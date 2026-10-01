// Debug-only: log RM register accesses into the ftrace buffer (/sys/kernel/tracing/trace).
// _nv052186rm = regWrite032(regAccess, devIdx, inst, addr=w3, val=w4, threadState)
// _nv052181rm = regRead032(regAccess, devIdx, inst, addr=w3, threadState) -> value
// v3: collapse repeated reads, printk P lines + MMU fault regs / NR fault packet dump during the hold.
// v4: map all 16M of BAR0 (PRAMIN @0x700000 was outside the 2M map -> v3 oopsed), PTE aperture 0 = vidmem,
//     walk watch_va in the PMU's VA space (pmu_pdb) at every TLB invalidate of that PDB + at the hold ("V" lines).
// v5: ceu=1: probes inside _nv042796rm = memmgrTestCeUtils (CE writes vid 0xAABBCCDD -> sysmem, CPU reads back,
//     mismatch -> NV_ERR_INVALID_STATE = the RmInitAdapter 0x40 failure). "C" lines: rc after each step, the
//     compared values, the kmap PA of the sysmem surface and its DRAM contents (linear map read before/after dc ivac).
// Tracefs kprobe events refuse these ("notrace"), raw kprobes don't.
#include <linux/module.h>
#include <linux/kprobes.h>
#include <linux/io.h>
#include <linux/delay.h>
#include <linux/ktime.h>

static bool reads = true;
module_param(reads, bool, 0444);
// probe=1: around RM's write to the PMU falcon ENGCTL (0x10a0a4) - snapshot GPU/PMU state, hold
// predelay_ms BEFORE the write (is the GPU already dead from the CE resets 0.4ms earlier?), then at
// RM's next register access sample every ~2us until BOOT0 reads all-ones (or sample_us passes).
static bool probe;
module_param(probe, bool, 0444);
static unsigned long bar0_phys = 0x1b80000000UL;
module_param(bar0_phys, ulong, 0444);
static uint predelay_ms = 20, sample_us = 20000;
module_param(predelay_ms, uint, 0444);
module_param(sample_us, uint, 0444);

static void __iomem *bar0;
static int armed;	/* 0 idle, 1 ENGCTL written -> sample at next access, 2 done */
static u64 t_wr;

#define PCFG 0x88078	/* PCI config mirror in BAR0 + exp cap 0x78 */
static const u32 snap_off[] = { 0x0, 0x200, 0x100, 0x10a100, 0x10a118, 0x10a0dc, 0x10a050, 0x10a008,
				0x10a16c, 0x100e60, PCFG + 0x8, PCFG + 0x10 };

static void snap(const char *tag)
{
	char buf[160]; int i, n = 0;
	for (i = 0; i < ARRAY_SIZE(snap_off); i++)
		n += scnprintf(buf + n, sizeof(buf) - n, " %08x", readl(bar0 + snap_off[i]));
	pr_info("nvrtrace: P %s BOOT0,EN,INTR,CPUCTL,DMATRFCMD,0dc,CURCTX,IRQSTAT,EXTERR,FLT,G_DEVSTA,G_LNK:%s\n", tag, buf);
}

/* sample BOOT0, DMATRFCMD, 0dc, CPUCTL, CURCTX; log each change with ns since the ENGCTL write */
static void sample_after(void)
{
	static const u32 o[] = { 0x0, 0x10a118, 0x10a0dc, 0x10a100, 0x10a050, 0x200 };
	u32 last[ARRAY_SIZE(o)] = { 0 }, v[ARRAY_SIZE(o)];
	u64 end = t_wr + (u64)sample_us * 1000, t;
	int i, ch, first = 1, n = 0;

	do {
		t = ktime_get_ns();
		for (i = 0, ch = first; i < ARRAY_SIZE(o); i++) {
			v[i] = readl(bar0 + o[i]);
			if (v[i] != last[i]) ch = 1;
		}
		if (ch && n++ < 200)
			trace_printk("S +%lluns BOOT0=%08x DMATRFCMD=%08x 0dc=%08x CPUCTL=%08x CURCTX=%08x EN=%08x\n",
				     t - t_wr, v[0], v[1], v[2], v[3], v[4], v[5]);
		memcpy(last, v, sizeof(v)); first = 0;
		if (v[0] == 0xffffffff) { trace_printk("S DEAD at +%lluns\n", t - t_wr); break; }
		udelay(2);
	} while (t < end);
	armed = 2;
}


/* v3: dump the MMU fault regs and the non-replayable fault buffer's pending packets (printk -> dmesg).
 * The NR buffer (0x100e24 lo/hi, GET 0x100e2c, PUT 0x100e30, SIZE 0x100e34) lives at a BAR2 VA: walk the
 * BAR2 page tables (V2, 5 levels) through PRAMIN (window 0x1700, aperture BAR0+0x700000), restoring 0x1700. */
static u32 vr32(u64 pa)
{
	u32 win = pa >> 16;
	if (readl(bar0 + 0x1700) != win) { writel(win, bar0 + 0x1700); readl(bar0 + 0x1700); }
	return readl(bar0 + 0x700000 + (pa & 0xffff));
}
static u64 vr64(u64 pa) { return vr32(pa) | ((u64)vr32(pa + 4) << 32); }
static u64 pde_addr(u64 e) { return ((e >> 8) & ((1ULL << 46) - 1)) << 12; }

/* Walk va from page directory pdb (vidmem; PDE aperture 1 = vidmem). Returns PA (PTE aperture in *ap:
 * 0 vid, 2 sys coh, 3 sys nc) or ~0. verbose: one "V" line with every level's entry. */
static u64 va2pa(const char *tag, u64 pdb, u64 va, int *ap, bool verbose)
{
	static const int sh[] = { 47, 38, 29 }, bits[] = { 2, 9, 9 };
	u64 tbl = pdb, e[3] = { 0 }, e0 = 0, e1 = 0, pte = 0, pa = ~0ULL;
	int l;

	for (l = 0; l < 3; l++) {
		e[l] = vr64(tbl + ((va >> sh[l]) & ((1 << bits[l]) - 1)) * 8);
		if (((e[l] >> 1) & 3) != 1) goto out;
		tbl = pde_addr(e[l]);
	}
	e0 = vr64(tbl + ((va >> 21) & 0xff) * 16);	/* big (64K) */
	e1 = vr64(tbl + ((va >> 21) & 0xff) * 16 + 8);	/* small (4K) */
	if (((e1 >> 1) & 3) == 1) {
		pte = vr64(pde_addr(e1) + ((va >> 12) & 0x1ff) * 8);
		if (pte & 1) { *ap = (pte >> 1) & 3; pa = pde_addr(pte) + (va & 0xfff); goto out; }
	}
	if (((e0 >> 1) & 3) == 1) {
		pte = vr64(pde_addr(e0) + ((va >> 16) & 0x1f) * 8);
		if (pte & 1) { *ap = (pte >> 1) & 3; pa = pde_addr(pte) + (va & 0xffff); }
	}
out:
	if (verbose || pa == ~0ULL)
		pr_info("nvrtrace: V %s pdb %llx va %llx: PD3 %016llx PD2 %016llx PD1 %016llx PD0 big %016llx small %016llx PTE %016llx -> %llx ap%d\n",
			tag, pdb, va, e[0], e[1], e[2], e0, e1, pte, pa, pa == ~0ULL ? -1 : *ap);
	return pa;
}

static u64 inst_pdb(u64 inst)
{
	u32 lo = vr32(inst + 0x200);
	return ((u64)vr32(inst + 0x204) << 32) | (lo & ~0xfffu);
}

static unsigned long pmu_pdb = 0x7fdf7d000UL, watch_va = 0x4010000UL;
module_param(pmu_pdb, ulong, 0444);
module_param(watch_va, ulong, 0444);

static void pmu_walk(const char *tag)
{
	u32 win = readl(bar0 + 0x1700);
	int ap = 0;

	va2pa(tag, pmu_pdb, watch_va, &ap, true);
	writel(win, bar0 + 0x1700); readl(bar0 + 0x1700);
}

static unsigned long ib_bus = 0x1000000000UL;	/* pcie1 inbound: CPU 0 -> bus 0x10_0000_0000 */
module_param(ib_bus, ulong, 0444);

static void fault_dump(const char *tag)
{
	u32 st = readl(bar0 + 0x100e60), lo = readl(bar0 + 0x100e24), hi = readl(bar0 + 0x100e28);
	u32 get = readl(bar0 + 0x100e2c), put = readl(bar0 + 0x100e30), size = readl(bar0 + 0x100e34);
	u32 win = readl(bar0 + 0x1700), i, k, wv[8];
	u64 va, pa;
	int ap = 0;

	pr_info("nvrtrace: F %s STATUS=%08x ADDR=%08x_%08x INST=%08x_%08x INFO=%08x NRBUF lo=%08x hi=%08x get=%08x put=%08x size=%08x RBUF get=%08x put=%08x\n",
		tag, st, readl(bar0 + 0x100e50), readl(bar0 + 0x100e4c), readl(bar0 + 0x100e58),
		readl(bar0 + 0x100e54), readl(bar0 + 0x100e5c), lo, hi, get, put, size,
		readl(bar0 + 0x100e40), readl(bar0 + 0x100e44));
	if ((get & 0xfffff) == (put & 0xfffff))
		return;
	for (i = get & 0xfffff; i != (put & 0xfffff) && i < (get & 0xfffff) + 4; i = (i + 1) % (size & 0xfffff ?: 1)) {
		if (lo & 1) {	/* physical mode */
			ap = (lo >> 1) & 3; pa = (((u64)hi << 32) | (lo & ~0xfffu)) + i * 32;
		} else {
			va = (((u64)hi << 32) | (lo & ~0xfffu)) + i * 32;
			pa = va2pa("nrbuf", inst_pdb((u64)(readl(bar0 + 0x1714) & 0xfffffff) << 12), va, &ap, false);
			if (pa == ~0ULL) break;
		}
		if (ap == 0) {
			for (k = 0; k < 8; k++) wv[k] = vr32(pa + k * 4);
		} else {
			void *p = pa >= ib_bus ? memremap(pa - ib_bus, 32, MEMREMAP_WB) : NULL;
			if (!p) { pr_info("nvrtrace: F pkt %u in sysmem bus %llx (ap %d), can't map\n", i, pa, ap); break; }
			memcpy(wv, p, 32); memunmap(p);
		}
		pr_info("nvrtrace: F pkt %u @%llx ap%d: %08x %08x %08x %08x %08x %08x %08x %08x\n",
			i, pa, ap, wv[0], wv[1], wv[2], wv[3], wv[4], wv[5], wv[6], wv[7]);
	}
	writel(win, bar0 + 0x1700); readl(bar0 + 0x1700);
}

static u32 last_cb8, n_inval;

static int wr_pre(struct kprobe *p, struct pt_regs *r)
{
	u32 a = (u32)r->regs[3], val = (u32)r->regs[4];

	if (probe && armed == 1) sample_after();
	trace_printk("W %06x=%08x\n", a, val);
	if (probe && bar0 && a == 0x100cb8) last_cb8 = val;
	if (probe && bar0 && armed != 1 && a == 0x100cbc && last_cb8 == (u32)((pmu_pdb >> 12) << 4)) {
		char tag[32];
		snprintf(tag, sizeof(tag), "inval#%u", ++n_inval);
		pmu_walk(tag);
	}
	if (probe && bar0 && !armed && a == 0x10a0a4) {
		snap("pre-engctl");
		fault_dump("pre-engctl");
		pmu_walk("pre-engctl");
		mdelay(predelay_ms);
		snap("pre-engctl+delay");
		fault_dump("pre-engctl+delay");
		pmu_walk("pre-engctl+delay");
		t_wr = ktime_get_ns();
		armed = 1;
	}
	return 0;
}

struct rd_data { u32 addr; };

static int rd_entry(struct kretprobe_instance *ri, struct pt_regs *r)
{
	((struct rd_data *)ri->data)->addr = (u32)r->regs[3];
	if (probe && armed == 1) sample_after();
	return 0;
}

/* v3: identical consecutive reads (RM poll loops) are collapsed: "R addr:val xN" when the run ends */
static u32 rd_last_a, rd_last_v, rd_rep;

static int rd_ret(struct kretprobe_instance *ri, struct pt_regs *r)
{
	u32 a = ((struct rd_data *)ri->data)->addr, v = (u32)regs_return_value(r);

	if (a == rd_last_a && v == rd_last_v) {
		if (++rd_rep % 100000 == 0)
			trace_printk("R %06x:%08x x%u (still polling)\n", a, v, rd_rep);
		return 0;
	}
	if (rd_rep)
		trace_printk("R %06x:%08x x%u\n", rd_last_a, rd_last_v, rd_rep);
	rd_rep = 0; rd_last_a = a; rd_last_v = v;
	trace_printk("R %06x:%08x\n", a, v);
	return 0;
}

static struct kprobe kp_wr = { .symbol_name = "nvidia:_nv052186rm", .pre_handler = wr_pre };
static struct kretprobe krp_rd = {
	.kp.symbol_name = "nvidia:_nv052181rm", .entry_handler = rd_entry, .handler = rd_ret,
	.data_size = sizeof(struct rd_data), .maxactive = 16,
};

/* ---- v5: memmgrTestCeUtils (_nv042796rm @ nv-kernel.o 0x483ec0) ---- */
static bool ceu = true;
module_param(ceu, bool, 0444);
static int ceu_in;
static u64 ceu_pa[8]; static void *ceu_va[8]; static int ceu_nk;

static const struct { u32 off; const char *what; } ceu_pts[] = {
	{ 0x000, "enter" }, { 0x154, "chan-alloc" }, { 0x1c8, "vid-create" }, { 0x1e0, "vid-alloc" },
	{ 0x214, "sys-create" }, { 0x22c, "sys-alloc" }, { 0x254, "memset-vid(CE)" }, { 0x274, "write-vid(CPU)" },
	{ 0x294, "write-sys(CPU)" }, { 0x2b4, "copy-vid>sys(CE)" }, { 0x2d4, "read-sys(CPU)" }, { 0x2e0, "compare" },
};
static struct kprobe kp_ceu[ARRAY_SIZE(ceu_pts)];

static u32 rd_line(void *va, bool inval)
{
	if (inval) { asm volatile("dc ivac, %0" :: "r"(va) : "memory"); dsb(sy); }
	return READ_ONCE(*(u32 *)va);
}

static int ceu_pre(struct kprobe *p, struct pt_regs *r)
{
	int i = p - kp_ceu, k;

	if (i == 0) { ceu_in = 1; ceu_nk = 0; trace_printk("C enter\n"); pr_info("nvrtrace: C enter\n"); return 0; }
	if (i < ARRAY_SIZE(ceu_pts) - 1) {
		trace_printk("C %s rc=%x\n", ceu_pts[i].what, (u32)r->regs[0]);
		pr_info("nvrtrace: C %s rc=%x\n", ceu_pts[i].what, (u32)r->regs[0]);
		return 0;
	}
	/* compare: w0 = vidmemData, w1 = sysmemData as read back by the CPU */
	trace_printk("C compare vid=%08x sys(readback)=%08x\n", (u32)r->regs[0], (u32)r->regs[1]);
	pr_info("nvrtrace: C compare vid=%08x sys(readback)=%08x %s\n", (u32)r->regs[0], (u32)r->regs[1],
		(u32)r->regs[0] == (u32)r->regs[1] ? "MATCH" : "MISMATCH");
	for (k = 0; k < ceu_nk; k++) {
		void *lin;
		if (!ceu_pa[k] || !pfn_valid(PHYS_PFN(ceu_pa[k]))) continue;
		lin = phys_to_virt(ceu_pa[k]);
		pr_info("nvrtrace: C kmap#%d va %px pa %llx (bus %llx): linear-map read %08x, after dc ivac (DRAM) %08x\n",
			k, ceu_va[k], ceu_pa[k], ceu_pa[k] + ib_bus, rd_line(lin, false), rd_line(lin, true));
	}
	ceu_in = 0;
	return 0;
}

static int km_ret(struct kretprobe_instance *ri, struct pt_regs *r)
{
	void *va = (void *)regs_return_value(r);
	struct page *pg;
	u64 pa = 0;

	if (!ceu_in || !va) return 0;
	pg = is_vmalloc_addr(va) ? vmalloc_to_page(va) : virt_addr_valid(va) ? virt_to_page(va) : NULL;
	if (pg) pa = page_to_phys(pg) + offset_in_page(va);
	trace_printk("C kmap va %px pa %llx\n", va, pa);
	pr_info("nvrtrace: C kmap va %px pa %llx\n", va, pa);
	if (ceu_nk < ARRAY_SIZE(ceu_pa)) { ceu_va[ceu_nk] = va; ceu_pa[ceu_nk++] = pa; }
	return 0;
}

static struct kretprobe krp_km = {
	.kp.symbol_name = "nvidia:nv_alloc_kernel_mapping", .handler = km_ret, .maxactive = 8,
};

static void ceu_unreg(int n)
{
	while (n--) unregister_kprobe(&kp_ceu[n]);
}

static int ceu_reg(void)
{
	int i, ret;

	for (i = 0; i < ARRAY_SIZE(ceu_pts); i++) {
		kp_ceu[i].symbol_name = "nvidia:_nv042796rm";
		kp_ceu[i].offset = ceu_pts[i].off;
		kp_ceu[i].pre_handler = ceu_pre;
		if ((ret = register_kprobe(&kp_ceu[i]))) {
			pr_err("nvrtrace: ceu probe +%x: %d\n", ceu_pts[i].off, ret);
			ceu_unreg(i);
			return ret;
		}
	}
	if ((ret = register_kretprobe(&krp_km))) {
		pr_err("nvrtrace: kmap probe %d\n", ret);
		ceu_unreg(ARRAY_SIZE(ceu_pts));
	}
	return ret;
}

static bool dump_now;
module_param(dump_now, bool, 0444);

static int __init nvrtrace_init(void)
{
	int ret;

	if (probe && !(bar0 = ioremap(bar0_phys, 0x1000000))) return -ENOMEM;
	if (dump_now) {	/* test: dump fault state and exit (needs probe=1) */
		if (bar0) { fault_dump("now"); pmu_walk("now"); iounmap(bar0); }
		return -EAGAIN;
	}
	ret = register_kprobe(&kp_wr);
	if (ret) { pr_err("nvrtrace: wr probe %d\n", ret); goto out_unmap; }
	if (reads && (ret = register_kretprobe(&krp_rd))) {
		pr_err("nvrtrace: rd probe %d\n", ret);
		unregister_kprobe(&kp_wr);
		goto out_unmap;
	}
	if (ceu && (ret = ceu_reg())) {
		if (reads) unregister_kretprobe(&krp_rd);
		unregister_kprobe(&kp_wr);
		goto out_unmap;
	}
	pr_info("nvrtrace: on (reads=%d probe=%d ceu=%d)\n", reads, probe, ceu);
	return 0;
out_unmap:
	if (bar0) iounmap(bar0);
	return ret;
}

static void __exit nvrtrace_exit(void)
{
	if (ceu) { unregister_kretprobe(&krp_km); ceu_unreg(ARRAY_SIZE(ceu_pts)); }
	if (reads)
		unregister_kretprobe(&krp_rd);
	unregister_kprobe(&kp_wr);
	if (bar0) iounmap(bar0);
}

module_init(nvrtrace_init);
module_exit(nvrtrace_exit);
MODULE_LICENSE("GPL");
