; nes.inc — NES hardware register constants (shared by all modules).

; --- PPU ---
PPUCTRL   = $2000
PPUMASK   = $2001
PPUSTATUS = $2002
OAMADDR   = $2003
OAMDATA   = $2004
PPUSCROLL = $2005
PPUADDR   = $2006
PPUDATA   = $2007

; --- APU / DMA / input ---
OAMDMA    = $4014
APUSTATUS = $4015
JOYPAD1   = $4016
JOYPAD2   = $4017   ; also APU frame counter

; --- Shadow OAM page (DMA source) ---
OAM_BUF   = $0200
