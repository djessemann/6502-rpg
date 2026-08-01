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

.import TitleEnter, TitleTick, SaveGame, LoadGame
.export GameInit, GameFrame
.export RowSlot, DecodeRow, BuildRowStrip, AttrRowShadow, QueueAttrRow
.export AttrRowForce
.export StartNewGame, StartLoadedGame

.segment "ENGINE"

; TEST_NO_TITLE builds the same ROM with the title module never called: the
; negative control t_titlescreen.py measures its boot frame against.
.proc GameInit
.ifdef TEST_SAVE_ROUNDTRIP
    jmp SaveRoundTrip
.endif
.ifdef TEST_PRESTAMP_SAVE
    jsr Pattern                 ; boot with a file already in the battery, so
    lda #TITLE_BANK             ; the title has a CONTINUE to offer
    jsr SetPrgCode
    jsr SaveGame
.endif
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

; The save file, end to end, without a terminal to talk to: write a pattern
; over the live state, save it, scribble the live state, load it back, and
; compare. Halts green on a match, red on a mismatch, amber if the file did not
; checksum at all.
;
; This proves the copy and the checksum. It does NOT prove that the battery
; survives a power cycle -- pyntendo has no cartridge-battery file, so nothing
; here can. The ROM's iNES header sets the battery bit (flags6 = $43), which is
; what makes FCEUX and Mesen write a .sav; verifying that end of it needs one
; of those emulators.
.proc SaveRoundTrip
    jsr Pattern                 ; a pattern no zero-fill can imitate
    lda #TITLE_BANK
    jsr SetPrgCode
    jsr SaveGame

    lda #$00                    ; wreck the live state, but not the slot
    jsr FillLive

.ifdef TEST_CORRUPT_SAVE
    inc slot_data+9             ; one bit-flip in the file: the checksum must
.endif                          ; notice, and LoadGame must refuse

    lda #TITLE_BANK
    jsr SetPrgCode
    jsr LoadGame
    bcc @nofile

    ldx #0
@cmp0:
    txa
    eor #$5A
    cmp sav_version,x
    bne @bad
    inx
    bne @cmp0
    ldx #0
@cmp1:
    txa
    eor #$A5
    cmp sav_version+256,x
    bne @bad
    inx
    cpx #SLOT_LEN-256
    bne @cmp1
    lda #$2A                    ; green: restored byte for byte
    jmp Halt
@bad:
    lda #$16                    ; red
    jmp Halt
@nofile:
    lda #$28                    ; amber: saved, then would not checksum
    jmp Halt
.endproc

; Exactly the SLOT_LEN bytes the save file covers -- 506, not 512. Writing two
; whole pages would run into slot_magic and make this test pass or fail for the
; wrong reason.
.proc Pattern
    ldx #0
:   txa
    eor #$5A
    sta sav_version,x
    inx
    bne :-
    ldx #0
:   txa
    eor #$A5
    sta sav_version+256,x
    inx
    cpx #SLOT_LEN-256
    bne :-
    rts
.endproc

.proc FillLive
    sta tmp1
    ldx #0
:   lda tmp1
    sta sav_version,x
    inx
    bne :-
    ldx #0
:   lda tmp1
    sta sav_version+256,x
    inx
    cpx #SLOT_LEN-256
    bne :-
    rts
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
