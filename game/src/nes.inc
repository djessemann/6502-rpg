; nes.inc — NES hardware registers and MMC3 constants.

PPUCTRL     = $2000
PPUMASK     = $2001
PPUSTATUS   = $2002
OAMADDR     = $2003
OAMDATA     = $2004
PPUSCROLL   = $2005
PPUADDR     = $2006
PPUDATA     = $2007
OAMDMA      = $4014

APUPULSE1   = $4000
APUPULSE2   = $4004
APUTRI      = $4008
APUNOISE    = $400C
APUDMC      = $4010
APUSTATUS   = $4015
APUFRAME    = $4017

JOYPAD1     = $4016
JOYPAD2     = $4017

; --- MMC3 (mapper 4) ---------------------------------------------------------
MMC_SELECT  = $8000     ; bank select      (even address in $8000-$9FFE)
MMC_DATA    = $8001     ; bank data        (odd  address in $8001-$9FFF)
MMC_MIRROR  = $A000     ; 0 = vertical, 1 = horizontal
MMC_PRGRAM  = $A001     ; bit7 enable, bit6 write-protect
MMC_IRQLAT  = $C000
MMC_IRQREL  = $C001
MMC_IRQDIS  = $E000
MMC_IRQENA  = $E001

; Bank-select values. Bit7 = CHR A12 inversion (we always use 1), bit6 = PRG
; mode (0: R6->$8000, R7->$A000, fixed at $C000/$E000).
;
; With CHR inversion on, the pattern tables are laid out as:
;   $0000-$03FF  R2  1KB   BG tiles $00-$3F   resident font / window / UI
;   $0400-$07FF  R3  1KB   BG tiles $40-$7F   resident HUD / shared art
;   $0800-$0BFF  R4  1KB   BG tiles $80-$BF   area tileset A / monster 1
;   $0C00-$0FFF  R5  1KB   BG tiles $C0-$FF   area tileset B / monster 2
;   $1000-$17FF  R0  2KB   sprite tiles $00-$7F
;   $1800-$1FFF  R1  2KB   sprite tiles $80-$FF
CHR_INV     = $80
SEL_CHR0    = CHR_INV | 0     ; 2KB sprite bank at $1000
SEL_CHR1    = CHR_INV | 1     ; 2KB sprite bank at $1800
SEL_CHR2    = CHR_INV | 2     ; 1KB BG bank at $0000
SEL_CHR3    = CHR_INV | 3     ; 1KB BG bank at $0400
SEL_CHR4    = CHR_INV | 4     ; 1KB BG bank at $0800
SEL_CHR5    = CHR_INV | 5     ; 1KB BG bank at $0C00
SEL_PRG6    = CHR_INV | 6     ; 8KB PRG bank at $8000  (data window)
SEL_PRG7    = CHR_INV | 7     ; 8KB PRG bank at $A000  (code window)

; Controller bits, in the order the shift register returns them.
BTN_A       = %10000000
BTN_B       = %01000000
BTN_SELECT  = %00100000
BTN_START   = %00010000
BTN_UP      = %00001000
BTN_DOWN    = %00000100
BTN_LEFT    = %00000010
BTN_RIGHT   = %00000001
