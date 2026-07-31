; sound.s — the sound driver. Lives in PRG bank 24 ($A000 code window).
; Stub for now: the call sites exist from the first ROM (NMI ticks it every
; frame, including lag frames) so integrating the real driver never moves code.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"

.include "banks.inc"

.export SoundInit, SoundTick

.segment "BANK24"

.proc SoundInit
    lda #$0F
    sta APUSTATUS           ; enable pulse 1/2, triangle, noise
    lda #$30
    sta APUPULSE1+0
    sta APUPULSE2+0
    sta APUNOISE+0
    lda #$80
    sta APUTRI+0
    rts
.endproc

.proc SoundTick
    rts
.endproc
