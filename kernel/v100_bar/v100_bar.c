// SPDX-License-Identifier: GPL-2.0
/*
 * Map a V100 32GB behind the Raspberry Pi 5 external PCIe port.
 *
 * The V100's BAR1 is a fixed 32GB, but the Pi's pcie1 outbound window is only
 * 14GB, so Linux leaves BAR1/BAR3 unassigned. The v100-pcie overlay remaps
 * that window (CPU 0x18_0000_0000) to PCIe bus 0x8_0000_0000, which is 32GB
 * aligned. Here we program BAR1 to that bus address and expose only the first
 * bar1_gb of it to Linux (and so to the NVIDIA driver). BAR3 goes into the
 * 32-bit non-prefetchable window after BAR0, since anything else in the
 * prefetchable window would fall inside BAR1's 32GB decode range.
 *
 * Must be loaded before nvidia.ko.
 */
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/ioport.h>

static unsigned int bar1_gb = 8;
module_param(bar1_gb, uint, 0444);
MODULE_PARM_DESC(bar1_gb, "Size of BAR1 exposed to Linux in GB (power of 2, default 8)");

#define BAR1_BUS_ALIGN  (32ULL << 30)
#define NONPREF_WIN_SZ  (64ULL << 20)
#define BAR3_SZ         (32ULL << 20)
#define BAR3_OFF        (32ULL << 20)

static struct resource *find_host_window(struct pci_bus *bus, bool pref)
{
	struct resource *res;
	int i;

	pci_bus_for_each_resource(bus, res, i) {
		if (res && (res->flags & IORESOURCE_MEM) &&
		    !!(res->flags & IORESOURCE_PREFETCH) == pref)
			return res;
	}
	return NULL;
}

static u64 cpu_to_bus(struct pci_dev *dev, resource_size_t addr)
{
	struct pci_bus_region region;
	struct resource tmp = DEFINE_RES_MEM(addr, 1);

	pcibios_resource_to_bus(dev->bus, &region, &tmp);
	return region.start;
}

static int v100_fix(struct pci_dev *gpu)
{
	struct pci_dev *br = gpu->bus->self;
	struct resource *host_pref, *br_pref, *br_mem, *r0, *r1, *r3;
	u64 bar1_size = (u64)bar1_gb << 30;
	u64 b1_bus, b3_bus, pref_end_bus, mem_bus, mem_end_bus;
	unsigned long lowbits;
	u16 cmd;
	int ret;

	if (!br || !pci_is_root_bus(br->bus)) {
		pci_err(gpu, "v100_bar: expected GPU directly behind the root port\n");
		return -ENODEV;
	}
	if (!is_power_of_2(bar1_size) || bar1_size > (16ULL << 30))
		return -EINVAL;

	r0 = &gpu->resource[0];
	r1 = &gpu->resource[1];
	r3 = &gpu->resource[3];
	br_mem = &br->resource[PCI_BRIDGE_MEM_WINDOW];
	br_pref = &br->resource[PCI_BRIDGE_PREF_MEM_WINDOW];

	if (r1->parent) {
		pci_info(gpu, "v100_bar: BAR1 already assigned %pR, nothing to do\n", r1);
		return 0;
	}
	if (!r0->parent || !br_mem->parent) {
		pci_err(gpu, "v100_bar: BAR0/bridge mem window not assigned\n");
		return -ENODEV;
	}

	host_pref = find_host_window(br->bus, true);
	if (!host_pref || resource_size(host_pref) < bar1_size) {
		pci_err(gpu, "v100_bar: no usable prefetchable host window\n");
		return -ENOSPC;
	}
	b1_bus = cpu_to_bus(br, host_pref->start);
	if (b1_bus & (BAR1_BUS_ALIGN - 1)) {
		pci_err(gpu, "v100_bar: host pref window %pR is at bus 0x%llx, not 32GB aligned (is the v100-pcie overlay loaded?)\n",
			host_pref, b1_bus);
		return -EINVAL;
	}

	pci_lock_rescan_remove();

	/* Memory decoding off while we move things around. */
	pci_read_config_word(gpu, PCI_COMMAND, &cmd);
	pci_write_config_word(gpu, PCI_COMMAND, cmd & ~PCI_COMMAND_MEMORY);

	/* Root port prefetchable window = exactly the exposed part of BAR1. */
	if (br_pref->parent)
		release_resource(br_pref);
	br_pref->start = host_pref->start;
	br_pref->end = host_pref->start + bar1_size - 1;
	br_pref->flags = IORESOURCE_MEM | IORESOURCE_PREFETCH | IORESOURCE_MEM_64;
	ret = request_resource(host_pref, br_pref);
	if (ret) {
		pci_err(br, "v100_bar: can't claim pref window %pR\n", br_pref);
		goto out;
	}

	/* Grow the non-prefetchable window to hold BAR0 (16M) + BAR3 (32M). */
	if (resource_size(br_mem) < NONPREF_WIN_SZ) {
		ret = adjust_resource(br_mem, br_mem->start, NONPREF_WIN_SZ);
		if (ret) {
			pci_err(br, "v100_bar: can't grow mem window %pR\n", br_mem);
			goto out;
		}
	}

	/* BAR1: keep BAR type bits, shrink the Linux-visible size. */
	lowbits = r1->flags & 0xf;
	r1->start = br_pref->start;
	r1->end = br_pref->end;
	r1->flags = IORESOURCE_MEM | IORESOURCE_PREFETCH | IORESOURCE_MEM_64 |
		    IORESOURCE_SIZEALIGN | (lowbits ? lowbits : 0xc);
	r1->name = pci_name(gpu);
	ret = request_resource(br_pref, r1);
	if (ret)
		goto out;

	/* BAR3 in the non-prefetchable window. Keep the 64-bit/pref type bits,
	 * nvidia.ko uses them to skip the upper half of the BAR. */
	lowbits = r3->flags & 0xf;
	r3->start = br_mem->start + BAR3_OFF;
	r3->end = r3->start + BAR3_SZ - 1;
	r3->flags = IORESOURCE_MEM | IORESOURCE_MEM_64 | IORESOURCE_SIZEALIGN |
		    (lowbits ? lowbits : 0xc);
	r3->name = pci_name(gpu);
	ret = request_resource(br_mem, r3);
	if (ret)
		goto out;

	/* Program the root port windows. */
	mem_bus = cpu_to_bus(br, br_mem->start);
	mem_end_bus = cpu_to_bus(br, br_mem->end);
	pci_write_config_word(br, PCI_MEMORY_BASE, (mem_bus >> 16) & 0xfff0);
	pci_write_config_word(br, PCI_MEMORY_LIMIT, (mem_end_bus >> 16) & 0xfff0);

	pref_end_bus = b1_bus + bar1_size - 1;
	pci_write_config_dword(br, PCI_PREF_BASE_UPPER32, b1_bus >> 32);
	pci_write_config_dword(br, PCI_PREF_LIMIT_UPPER32, pref_end_bus >> 32);
	pci_write_config_word(br, PCI_PREF_MEMORY_BASE,
			      ((b1_bus >> 16) & 0xfff0) | PCI_PREF_RANGE_TYPE_64);
	pci_write_config_word(br, PCI_PREF_MEMORY_LIMIT,
			      ((pref_end_bus >> 16) & 0xfff0) | PCI_PREF_RANGE_TYPE_64);

	/* Program the GPU BARs. */
	b3_bus = cpu_to_bus(gpu, r3->start);
	pci_write_config_dword(gpu, PCI_BASE_ADDRESS_1, lower_32_bits(b1_bus));
	pci_write_config_dword(gpu, PCI_BASE_ADDRESS_2, upper_32_bits(b1_bus));
	pci_write_config_dword(gpu, PCI_BASE_ADDRESS_3, lower_32_bits(b3_bus));
	pci_write_config_dword(gpu, PCI_BASE_ADDRESS_4, upper_32_bits(b3_bus));

	pci_info(gpu, "v100_bar: BAR1 %pR (bus 0x%llx, %u of 32 GB exposed), BAR3 %pR (bus 0x%llx)\n",
		 r1, b1_bus, bar1_gb, r3, b3_bus);
	ret = 0;
out:
	pci_write_config_word(gpu, PCI_COMMAND, cmd);
	pci_unlock_rescan_remove();
	return ret;
}

static int __init v100_bar_init(void)
{
	struct pci_dev *gpu = NULL;
	int ret = -ENODEV;

	while ((gpu = pci_get_device(PCI_VENDOR_ID_NVIDIA, PCI_ANY_ID, gpu))) {
		if ((gpu->class >> 8) != PCI_CLASS_DISPLAY_3D &&
		    (gpu->class >> 8) != PCI_CLASS_DISPLAY_VGA)
			continue;
		ret = v100_fix(gpu);
		pci_dev_put(gpu);
		break;
	}
	return ret;
}

static void __exit v100_bar_exit(void)
{
}

module_init(v100_bar_init);
module_exit(v100_bar_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Assign a truncated BAR1 for NVIDIA V100 on Raspberry Pi 5");
