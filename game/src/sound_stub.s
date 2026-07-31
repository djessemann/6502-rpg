; sound_stub.s — a silent stand-in for the driver, used when building while
; the real driver is being worked on.
.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"
.export SoundInit, SoundTick
.segment "BANK24"
.proc SoundInit
    lda #$0F
    sta APUSTATUS
    rts
.endproc
.proc SoundTick
    lda #0
    sta music_req
    sta sfx_req
    rts
.endproc
