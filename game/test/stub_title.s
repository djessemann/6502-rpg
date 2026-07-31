; stub_title.s — a harness that boots straight into src/title.s with no field
; engine behind it, so the title screen can be verified before it is wired in.
;
; Links kernel + text + title + the generated data, and stands in for the six
; field routines text.s calls and the two field entry points title.s jumps to.
; The entry points halt on a flat colour instead, so a test can tell which one
; the player reached.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"

.import TitleEnter, TitleTick
.export GameInit, GameFrame
.export RowSlot, DecodeRow, BuildRowStrip, AttrRowShadow, QueueAttrRow
.export AttrRowForce
.export StartNewGame, StartLoadedGame

.segment "ENGINE"

; TEST_NO_TITLE builds the same ROM with the title module never called: the
; negative control t_titlescreen.py measures its boot frame against.
.proc GameInit
.ifndef TEST_NO_TITLE
    lda #TITLE_BANK
    jsr SetPrgCode
    jmp TitleEnter
.else
    jmp ScreenOn
.endif
.endproc

.proc GameFrame
.ifndef TEST_NO_TITLE
    lda #TITLE_BANK
    jsr SetPrgCode
    jmp TitleTick
.else
    rts
.endif
.endproc

; The two ways out of the title. Each stops on a colour the test can name, so
; "did MAKE PLANETFALL fire" is a question about pixels and not about a hang.
.proc StartNewGame
    lda #$2A                    ; green
    jmp Halt
.endproc

.proc StartLoadedGame
    lda #$12                    ; blue
    jmp Halt
.endproc

.proc Halt
    sta tmp0
    sei
    lda #0
    sta PPUMASK
    sta PPUCTRL
    sta ppu_ctrl
    sta ppu_mask
    lda #$3F
    ldx #$00
    jsr PpuAddr
    ldx #32
    lda tmp0
    jsr PpuFill
    lda #$3F
    ldx #$00
    jsr PpuAddr
    lda #%00011110
    sta PPUMASK
    jmp *
.endproc

; --- what text.s expects the field engine to provide -------------------------
; The title screen draws its own rows and never asks text.s for a map row, so
; these only have to link.
.proc RowSlot
    rts
.endproc
.proc DecodeRow
    rts
.endproc
.proc BuildRowStrip
    rts
.endproc
.proc AttrRowShadow
    rts
.endproc
.proc QueueAttrRow
    rts
.endproc
.proc AttrRowForce
    rts
.endproc

.import SetPrgCode, PpuAddr, PpuFill, ScreenOn
