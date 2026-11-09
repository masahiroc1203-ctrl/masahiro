//go:build linux || darwin || freebsd

package main

import "syscall"

// diskSpace はバックアップ先の空き容量と全体容量を返す。
func diskSpace(dir string) (free, total uint64, ok bool) {
	var st syscall.Statfs_t
	if err := syscall.Statfs(dir, &st); err != nil {
		return 0, 0, false
	}
	bs := uint64(st.Bsize)
	return uint64(st.Bavail) * bs, uint64(st.Blocks) * bs, true
}
