; kernel.s — THRENOS kernel. Lives in PRG bank 31, fixed at $E000-$FFFF.
;
; Owns: reset, the split game loop, the NMI render pipeline, MMC3 banking,
; the VBUF transfer queue, controller input, RNG and integer math. Nothing here
; ever moves; every other bank may call into it.

.include "nes.inc"
.include "zp.inc"
.include "ram.inc"
.include "banks.inc"

.import GameInit, GameFrame
.import SoundInit, SoundTick

.export SetPrgData, SetPrgCode, SetChrBank, WaitFrame, ReadInput
.export VBufReset, VBufAlloc, Random, Rand16, Mul8, Div8, Div16
.export PpuAddr, PpuFill, ClearNametables, LoadPalette, MemClear, MemCopy
.export FarCall, FarCallRet, WaitVBlank, ScreenOff, ScreenOn, SetMirror

; Default CHR banks (1KB units) at boot.
CHR_FONT_BANK  = 0
CHR_UI_BANK    = 1
CHR_SPR0_BANK  = 88     ; 2KB sprite bank at $1000 (1KB index, bit0 ignored)
CHR_SPR1_BANK  = 90     ; 2KB sprite bank at $1800

.segment "KERNEL"

; -----------------------------------------------------------------------------
; RESET
; -----------------------------------------------------------------------------
.proc RESET
    sei
    cld
    ldx #$40
    stx JOYPAD2             ; disable APU frame IRQ
    ldx #$FF
    txs
    inx                     ; X = 0
    stx PPUCTRL             ; NMI off
    stx PPUMASK             ; rendering off
    stx APUSTATUS
    lda #$00
    sta APUDMC              ; no DMC IRQ

    ; MMC3: disable its scanline IRQ before anything else can fire one.
    sta MMC_IRQDIS

    bit PPUSTATUS
:   bit PPUSTATUS           ; first vblank
    bpl :-

    ; --- MMC3 configuration --------------------------------------------------
    lda #0
    sta MMC_MIRROR          ; vertical mirroring (two nametables side by side)
    lda #$80
    sta MMC_PRGRAM          ; PRG-RAM enabled, writable

    lda #CHR_SPR0_BANK
    ldx #SEL_CHR0
    jsr SetChrBank
    lda #CHR_SPR1_BANK
    ldx #SEL_CHR1
    jsr SetChrBank
    lda #CHR_FONT_BANK
    ldx #SEL_CHR2
    jsr SetChrBank
    lda #CHR_UI_BANK
    ldx #SEL_CHR3
    jsr SetChrBank
    lda #2
    ldx #SEL_CHR4
    jsr SetChrBank
    lda #3
    ldx #SEL_CHR5
    jsr SetChrBank
    lda #0
    jsr SetPrgData
    lda #24
    jsr SetPrgCode

    ; --- clear RAM -----------------------------------------------------------
    lda #$00
    ldx #$00
@clr:
    sta $0000,x
    sta $0100,x
    sta $0300,x
    sta $0400,x
    sta $0500,x
    sta $0600,x
    sta $0700,x
    lda #$FF
    sta $0200,x             ; unused sprites off-screen
    lda #$00
    inx
    bne @clr

    ; clear work RAM $6800-$7FFF (the save area $6000-$67FF is left alone)
    lda #<$6800
    sta ptr
    lda #>$6800
    sta ptr+1
    ldx #24                 ; 24 pages
    ldy #0
    lda #0
@wclr:
    sta (ptr),y
    iny
    bne @wclr
    inc ptr+1
    dex
    bne @wclr

:   bit PPUSTATUS           ; second vblank; PPU is ready
    bpl :-

    ; --- PPU initial state ---------------------------------------------------
    ; NMI stays OFF until ScreenOn turns it on: the shadow must always match
    ; the register, because ScreenOff decides how to wait on bit 7.
    lda #%00001000          ; BG table $0000, sprite table $1000, NMI off
    sta ppu_ctrl
    lda #%00011110
    sta ppu_mask
    lda #$00
    sta scroll_x
    sta scroll_y

    jsr ClearNametables

    ; seed the RNG with something that is not zero
    lda #$A5
    sta rng
    lda #$3C
    sta rng+1

    jsr VBufReset
    jsr SoundInit
    jsr GameInit            ; engine bank ($C000, always mapped)
                            ; (GameInit's DrawFullMap ends in ScreenOn, which
                            ; is what enables NMI and rendering)
    ; fall through
.endproc

; -----------------------------------------------------------------------------
; MAIN — the game-logic thread. Never touches the PPU.
; -----------------------------------------------------------------------------
.proc MAIN
@loop:
    jsr ReadInput
    jsr VBufReset
    jsr GameFrame
    jsr WaitFrame
    jmp @loop
.endproc

; -----------------------------------------------------------------------------
; NMI — the only per-frame PPU writer.
; -----------------------------------------------------------------------------
.proc NMI
    pha
    txa
    pha
    tya
    pha

    ; OAM DMA first: it must happen early in vblank.
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    jsr FlushVBuf

    ; Restore the scroll after the $2006 writes above.
    bit PPUSTATUS
    lda ppu_ctrl
    sta PPUCTRL
    lda scroll_x
    sta PPUSCROLL
    lda scroll_y
    sta PPUSCROLL
    lda ppu_mask
    sta PPUMASK

    ; The sound driver ticks every frame, including lag frames. It lives in its
    ; own bank; save and restore whatever the main thread had mapped.
    lda cur_code_bank
    pha
    lda #SOUND_BANK
    jsr SetPrgCode
    jsr SoundTick
    pla
    jsr SetPrgCode

    inc frame_count
    pla
    tay
    pla
    tax
    pla
    rti
.endproc

; -----------------------------------------------------------------------------
; IRQ — MMC3 scanline IRQ (unused for now).
; -----------------------------------------------------------------------------
.proc IRQ
    rti
.endproc

; -----------------------------------------------------------------------------
; FlushVBuf — write the queued packets to VRAM. NMI only.
; -----------------------------------------------------------------------------
.proc FlushVBuf
    lda #<VBUF
    sta vram_ptr
    lda #>VBUF
    sta vram_ptr+1
@next:
    ldy #0
    lda (vram_ptr),y
    bne @go
    rts
@go:
    sta tmp0                ; mode
    cmp #2
    beq @col
    lda ppu_ctrl
    and #%11111011          ; VRAM address increment = 1
    jmp @setctrl
@col:
    lda ppu_ctrl
    ora #%00000100          ; VRAM address increment = 32
@setctrl:
    sta PPUCTRL
    bit PPUSTATUS
    iny
    lda (vram_ptr),y
    sta PPUADDR
    iny
    lda (vram_ptr),y
    sta PPUADDR
    iny
    lda (vram_ptr),y
    sta tmp1                ; count
    iny
    ldx tmp1
    lda tmp0
    cmp #3
    beq @fill
@copy:
    lda (vram_ptr),y
    sta PPUDATA
    iny
    dex
    bne @copy
    jmp @adv
@fill:
    lda (vram_ptr),y
:   sta PPUDATA
    dex
    bne :-
    iny
@adv:
    tya
    clc
    adc vram_ptr
    sta vram_ptr
    bcc @next
    inc vram_ptr+1
    jmp @next
.endproc

; -----------------------------------------------------------------------------
; VBufReset — empty the transfer queue (called once per frame by MAIN).
; -----------------------------------------------------------------------------
.proc VBufReset
    lda #<VBUF
    sta vbuf_wp
    lda #>VBUF
    sta vbuf_wp+1
    lda #0
    ldy #0
    sta (vbuf_wp),y
    rts
.endproc

; -----------------------------------------------------------------------------
; VBufAlloc — reserve a packet.
;   in:  vb_mode, vb_hi, vb_lo, vb_cnt
;   out: vb_dat -> the packet's data area, carry clear on success.
;        Carry set (and nothing reserved) if the queue is full.
; -----------------------------------------------------------------------------
.proc VBufAlloc
    ; needed = 4 + (mode 3 ? 1 : count)
    lda vb_mode
    cmp #3
    bne :+
    lda #1
    jmp @have
:   lda vb_cnt
@have:
    clc
    adc #4
    sta tmp0                ; packet size
    clc
    adc vbuf_wp
    sta tmp1
    lda vbuf_wp+1
    adc #0
    sta tmp2
    ; room check: end must be <= VBUF_END
    lda tmp2
    cmp #>VBUF_END
    bcc @ok
    bne @full
    lda tmp1
    cmp #<VBUF_END
    bcc @ok
@full:
    sec
    rts
@ok:
    ldy #0
    lda vb_mode
    sta (vbuf_wp),y
    iny
    lda vb_hi
    sta (vbuf_wp),y
    iny
    lda vb_lo
    sta (vbuf_wp),y
    iny
    lda vb_cnt
    sta (vbuf_wp),y
    lda vbuf_wp
    clc
    adc #4
    sta vb_dat
    lda vbuf_wp+1
    adc #0
    sta vb_dat+1
    ; advance the write pointer and re-terminate
    lda vbuf_wp
    clc
    adc tmp0
    sta vbuf_wp
    lda vbuf_wp+1
    adc #0
    sta vbuf_wp+1
    lda #0
    tay
    sta (vbuf_wp),y
    clc
    rts
.endproc

; -----------------------------------------------------------------------------
; Banking
; -----------------------------------------------------------------------------
; A = 8KB PRG bank for the $8000 window (data). X and Y are preserved: bank
; switches happen inside loops all over the engine.
.proc SetPrgData
    sta cur_data_bank
    pha
    lda #SEL_PRG6
    sta MMC_SELECT
    pla
    sta MMC_DATA
    rts
.endproc

; A = 8KB PRG bank for the $A000 window (code). X and Y are preserved.
.proc SetPrgCode
    sta cur_code_bank
    pha
    lda #SEL_PRG7
    sta MMC_SELECT
    pla
    sta MMC_DATA
    rts
.endproc

; X = SEL_CHRn select value, A = bank number.
.proc SetChrBank
    stx MMC_SELECT
    sta MMC_DATA
    rts
.endproc

; A = 0 vertical / 1 horizontal
.proc SetMirror
    sta MMC_MIRROR
    rts
.endproc

; Call a routine in the $A000 code window.
;   A = bank, ptr = target address. The target's RTS returns to our caller.
.proc FarCall
    jsr SetPrgCode
    jmp (ptr)
.endproc

; Call a routine in ANOTHER $A000 code bank and come back to the caller's.
; Two code banks share the $A000 window, so a plain jsr from one into the other
; unmaps the caller mid-call; this trampoline runs from the fixed kernel bank,
; so it survives the switch in both directions.
;   in:  ptr = the target's address, far_bank = the bank it lives in.
;        A, X and Y are passed through to the target untouched.
;   out: the target's A, X and Y; the caller's code bank restored.
.proc FarCallRet
    pha
    lda cur_code_bank
    sta far_ret
    lda far_bank
    jsr SetPrgCode              ; X and Y are preserved by SetPrgCode
    pla
    jsr @call
    pha
    lda far_ret
    jsr SetPrgCode
    pla
    rts
@call:
    jmp (ptr)
.endproc

; -----------------------------------------------------------------------------
; Frame sync
; -----------------------------------------------------------------------------
.proc WaitFrame
    lda frame_count
:   cmp frame_count
    beq :-
    rts
.endproc

.proc WaitVBlank
    bit PPUSTATUS
:   bit PPUSTATUS
    bpl :-
    rts
.endproc

; Turn rendering and NMI off, for a full-screen repaint.
;
; NEVER poll PPUSTATUS for vblank while NMI is enabled: the handler reads
; PPUSTATUS first and clears the flag, so the poll would spin forever. When NMI
; is on we hand the job to it (it writes ppu_mask every frame) and wait on
; frame_count instead.
.proc ScreenOff
    lda ppu_ctrl
    bpl @nmi_off
    lda #0
    sta ppu_mask            ; NMI turns rendering off at the next vblank
    jsr WaitFrame
    lda ppu_ctrl
    and #%01111111
    sta ppu_ctrl
    sta PPUCTRL             ; safe now: rendering is already off
    rts
@nmi_off:
    lda #0
    sta ppu_mask
    sta PPUMASK
    sta PPUCTRL
    rts
.endproc

; Turn rendering and NMI back on. Always entered with NMI off, so polling
; PPUSTATUS here is safe.
.proc ScreenOn
    jsr WaitVBlank
    lda #%00011110
    sta ppu_mask
    lda ppu_ctrl
    ora #%10000000
    sta ppu_ctrl
    bit PPUSTATUS
    sta PPUCTRL
    lda scroll_x
    sta PPUSCROLL
    lda scroll_y
    sta PPUSCROLL
    lda ppu_mask
    sta PPUMASK
    rts
.endproc

; -----------------------------------------------------------------------------
; Controller
; -----------------------------------------------------------------------------
.proc ReadInput
    lda pad1
    sta pad1_prev
    lda #1
    sta JOYPAD1
    lda #0
    sta JOYPAD1
    ldx #8
@bit:
    lda JOYPAD1
    lsr a                   ; button state -> carry
    rol tmp0
    dex
    bne @bit
    lda tmp0
    sta pad1
    eor pad1_prev
    and pad1
    sta pad1_new
    rts
.endproc

; -----------------------------------------------------------------------------
; RNG — 16-bit Galois LFSR. Random returns a byte in A.
; -----------------------------------------------------------------------------
.proc Random
    jsr Rand16
    lda rng
    rts
.endproc

; X and Y are preserved: the RNG is called from inside indexed loops all over
; the battle code.
.proc Rand16
    txa
    pha
    ldx #8
    lda rng
@lp:
    asl a
    rol rng+1
    bcc :+
    eor #$2D
:   dex
    bne @lp
    sta rng
    pla
    tax
    lda rng
    rts
.endproc

; -----------------------------------------------------------------------------
; Math
; -----------------------------------------------------------------------------
; mul_res(16) = mul_a * mul_b   (8x8 -> 16)
.proc Mul8
    lda #0
    sta mul_res
    sta mul_res+1
    ldx #8
    lda mul_a
@lp:
    lsr a
    bcc :+
    pha
    lda mul_res+1
    clc
    adc mul_b
    sta mul_res+1
    pla
:   ror mul_res+1
    ror mul_res
    dex
    bne @lp
    rts
.endproc

; div_q = div_n / div_d, div_r = remainder. div_n is consumed.
.proc Div8
    lda #0
    sta div_r
    ldx #8
@lp:
    asl div_n
    rol div_r
    bcs @sub                ; remainder bit 8 set -> certainly >= divisor
    lda div_r
    cmp div_d
    bcc @no
@sub:
    lda div_r
    sec
    sbc div_d
    sta div_r
    inc div_n               ; quotient bit (just shifted in as 0)
@no:
    dex
    bne @lp
    lda div_n
    sta div_q
    lda #0
    sta div_q+1
    rts
.endproc

; div_q(16) = div_n(16) / div_d(8), div_r = remainder. div_n is consumed.
.proc Div16
    lda #0
    sta div_r
    ldx #16
@lp:
    asl div_n
    rol div_n+1
    rol div_r
    bcs @sub
    lda div_r
    cmp div_d
    bcc @no
@sub:
    lda div_r
    sec
    sbc div_d
    sta div_r
    inc div_n
@no:
    dex
    bne @lp
    lda div_n
    sta div_q
    lda div_n+1
    sta div_q+1
    rts
.endproc

; -----------------------------------------------------------------------------
; PPU helpers — safe only with rendering disabled (or inside NMI).
; -----------------------------------------------------------------------------
; A = address high, X = address low
.proc PpuAddr
    bit PPUSTATUS
    sta PPUADDR
    stx PPUADDR
    rts
.endproc

; Write A to PPUDATA, X times (X = 0 means 256).
.proc PpuFill
:   sta PPUDATA
    dex
    bne :-
    rts
.endproc

.proc ClearNametables
    lda #$20
    ldx #$00
    jsr PpuAddr
    ldy #16                 ; 16 * 256 = 4096 bytes = both nametables + attrs
    lda #$00
@page:
    ldx #0
    jsr PpuFill
    dey
    bne @page
    rts
.endproc

; ptr -> 32 bytes of palette data
.proc LoadPalette
    lda #$3F
    ldx #$00
    jsr PpuAddr
    ldy #0
:   lda (ptr),y
    sta PPUDATA
    iny
    cpy #32
    bne :-
    rts
.endproc

; Fill copy_len bytes at dstp with A.
.proc MemClear
    ldy #0
:   sta (dstp),y
    iny
    cpy copy_len
    bne :-
    rts
.endproc

; Copy copy_len bytes from srcp to dstp (copy_len = 0 means 256).
.proc MemCopy
    ldy #0
:   lda (srcp),y
    sta (dstp),y
    iny
    cpy copy_len
    bne :-
    rts
.endproc

; -----------------------------------------------------------------------------
.segment "VECTORS"
    .addr NMI, RESET, IRQ
