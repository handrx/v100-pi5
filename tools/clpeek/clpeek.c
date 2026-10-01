// clpeek: read RM's PDB_PROP_CL_IS_CHIPSET_IO_COHERENT byte (g_pSys->pCl + 106) and dump the
// OBJCL property bytes around it. psys = address of the blob's g_pSys variable (_nv028167rm, from /proc/kallsyms).
#include <linux/module.h>
#include <linux/uaccess.h>
static unsigned long psys;
module_param(psys, ulong, 0444);
static int __init clpeek_init(void)
{
	u64 sys = 0, cl = 0;
	u8 b[32];
	int i;
	if (!psys || get_kernel_nofault(sys, (u64 *)psys) || !sys ||
	    get_kernel_nofault(cl, (u64 *)(sys + 520)) || !cl) {
		pr_info("clpeek: psys=%lx sys=%llx cl=%llx: unreadable\n", psys, sys, cl);
		return -EINVAL;
	}
	for (i = 0; i < 32; i++)
		if (get_kernel_nofault(b[i], (u8 *)(cl + 96 + i)))
			return -EFAULT;
	pr_info("clpeek: pSys=%llx pCl=%llx IO_COHERENT[106]=%u DISABLE_IOMAP_WC[107]=%u\n", sys, cl, b[10], b[11]);
	pr_info("clpeek: pCl+96: %*ph\n", 32, b);
	return -EAGAIN;	/* never stays loaded */
}
module_init(clpeek_init);
MODULE_LICENSE("GPL");
