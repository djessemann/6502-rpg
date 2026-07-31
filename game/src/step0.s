; step0.s — engine-bank hardware proof (PRG banking, CHR banking, PRG-RAM).
; Lives in PRG bank 30 ($C000, always mapped). Replaced by the real engine once
; the platform is proven.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "gen/charmap.inc"

.import SetPrgData, SetChrBank, PpuAddr, LoadPalette
.import Div8
.export GameInit, GameFrame

prg_ok  = misc_bss + 0
ram_bad = misc_bss + 1

.segment "ENGINE"

.proc GameInit
    lda #<pal
    sta ptr
    lda #>pal
    sta ptr+1
    jsr LoadPalette

    jsr TestPrgBanks
    jsr TestPrgRam

    lda #<s_title
    sta ptr
    lda #>s_title
    sta ptr+1
    lda #2
    ldx #8
    jsr PrintAt

    lda #<s_prg
    sta ptr
    lda #>s_prg
    sta ptr+1
    lda #6
    ldx #4
    jsr PrintAt
    lda prg_ok
    jsr PrintNum

    lda #<s_ram
    sta ptr
    lda #>s_ram
    sta ptr+1
    lda #8
    ldx #4
    jsr PrintAt
    lda ram_bad
    jsr PrintNum

    ; CHR banking: BG tiles $80+ come from R4 (bank 2, a box), $C0+ from R5
    ; (bank 100, a diagonal). Both drawn side by side.
    lda #<s_chr
    sta ptr
    lda #>s_chr
    sta ptr+1
    lda #10
    ldx #4
    jsr PrintAt
    lda #$80
    sta PPUDATA
    sta PPUDATA
    lda #$00
    sta PPUDATA
    lda #$C0
    sta PPUDATA
    sta PPUDATA

    lda #2
    ldx #SEL_CHR4
    jsr SetChrBank
    lda #100
    ldx #SEL_CHR5
    jsr SetChrBank

    lda #<s_ready
    sta ptr
    lda #>s_ready
    sta ptr+1
    lda #14
    ldx #4
    jsr PrintAt
    rts
.endproc

; Every data bank must be reachable at $8000 and hold its signature byte.
.proc TestPrgBanks
    lda #0
    sta prg_ok
    ldx #0
@lp:
    txa
    jsr SetPrgData
    lda $8000
    sta tmp0
    txa
    eor #$5A
    cmp tmp0
    bne @bad
    inc prg_ok
@bad:
    inx
    cpx #24
    bne @lp
    lda #0
    jsr SetPrgData
    rts
.endproc

; Battery-backed PRG-RAM at $6000 must read back what it is given.
.proc TestPrgRam
    ldx #0
@w:
    txa
    eor #$C3
    sta $6400,x
    inx
    bne @w
    lda #0
    sta ram_bad
    ldx #0
@r:
    txa
    eor #$C3
    cmp $6400,x
    beq @ok
    inc ram_bad
@ok:
    inx
    bne @r
    rts
.endproc

; ptr -> string ($FF terminated), A = nametable row, X = column.
.proc PrintAt
    stx tmp3
    pha
    lsr a
    lsr a
    lsr a
    clc
    adc #$20
    sta tmp2
    pla
    and #7
    asl a
    asl a
    asl a
    asl a
    asl a
    ora tmp3
    tax
    lda tmp2
    jsr PpuAddr
    ldy #0
@lp:
    lda (ptr),y
    cmp #STR_END
    beq @done
    sta PPUDATA
    iny
    bne @lp
@done:
    rts
.endproc

; A = value -> three decimal digits at the current PPU address.
.proc PrintNum
    sta div_n
    lda #100
    sta div_d
    jsr Div8
    lda div_q
    clc
    adc #DIGIT0
    sta PPUDATA
    lda div_r
    sta div_n
    lda #10
    sta div_d
    jsr Div8
    lda div_q
    clc
    adc #DIGIT0
    sta PPUDATA
    lda div_r
    clc
    adc #DIGIT0
    sta PPUDATA
    rts
.endproc

.proc GameFrame
    rts
.endproc

.segment "ENGRO"
s_title:  .byte "THRENOS - STEP 0", STR_END
s_prg:    .byte "PRG BANKS OK: ", STR_END
s_ram:    .byte "PRG-RAM BAD BYTES: ", STR_END
s_chr:    .byte "CHR BANKS: ", STR_END
s_ready:  .byte "PLATFORM READY.", STR_END

pal:
    .byte $0F,$30,$21,$16
    .byte $0F,$27,$16,$06
    .byte $0F,$2A,$1A,$09
    .byte $0F,$30,$10,$00
    .byte $0F,$30,$21,$16
    .byte $0F,$27,$16,$06
    .byte $0F,$2A,$1A,$09
    .byte $0F,$30,$10,$00
