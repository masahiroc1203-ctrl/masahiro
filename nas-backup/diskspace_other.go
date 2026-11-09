//go:build !(linux || darwin || freebsd)

package main

// diskSpace はこの OS では未対応 (空き容量の表示が省略されるだけで動作には影響しない)。
func diskSpace(dir string) (free, total uint64, ok bool) {
	return 0, 0, false
}
