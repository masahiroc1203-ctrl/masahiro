//go:build windows

package main

import (
	"strings"
	"syscall"
	"unsafe"
)

var procGetDiskFreeSpaceEx = syscall.NewLazyDLL("kernel32.dll").NewProc("GetDiskFreeSpaceExW")

// diskSpace はバックアップ先の空き容量と全体容量を返す (\\NAS\share のようなネットワークパスにも対応)。
func diskSpace(dir string) (free, total uint64, ok bool) {
	if !strings.HasSuffix(dir, `\`) {
		dir += `\` // UNC パスは末尾の \ が必要
	}
	p, err := syscall.UTF16PtrFromString(dir)
	if err != nil {
		return 0, 0, false
	}
	var avail, tot, totalFree uint64
	r, _, _ := procGetDiskFreeSpaceEx.Call(
		uintptr(unsafe.Pointer(p)),
		uintptr(unsafe.Pointer(&avail)),
		uintptr(unsafe.Pointer(&tot)),
		uintptr(unsafe.Pointer(&totalFree)),
	)
	if r == 0 {
		return 0, 0, false
	}
	return avail, tot, true
}
