; main.s — boot, split game loop, and NMI render pipeline (Step 1: Boot).
;
; Structural contract (CLAUDE.md), in place from the first ROM:
;   * Split loop: all game logic runs in the main thread; every PPU update
;     happens in the NMI handler.
;   * PPU discipline: $2005/$2006/$2007 are only touched inside NMI (or while
;     rendering is disabled during init). Per-frame nametable/palette changes
;     will go through the VRAM buffer at $0300 and be flushed in NMI.
;   * Shadow OAM at $0200, copied to the PPU by DMA every frame in NMI.
;   * A sound tick is called every frame, including lag frames (stub for now,
;     but the call site exists).

.include "nes.inc"

; ----------------------------------------------------------------------------
; Zeropage variables
; ----------------------------------------------------------------------------
.segment "ZEROPAGE"
frame_count:  .res 1   ; incremented by NMI; main loop syncs against it

; ----------------------------------------------------------------------------
; Shadow OAM (DMA source page, $0200-$02FF)
; ----------------------------------------------------------------------------
.segment "OAMBUF"
oam:          .res 256

; ----------------------------------------------------------------------------
; RESET
; ----------------------------------------------------------------------------
.segment "CODE"
.proc RESET
    sei                 ; ignore IRQs
    cld                 ; NES has no decimal mode
    ldx #$40
    stx JOYPAD2         ; disable APU frame IRQ
    ldx #$FF
    txs                 ; set up stack
    inx                 ; X = 0
    stx PPUCTRL         ; disable NMI
    stx PPUMASK         ; disable rendering
    stx APUSTATUS       ; disable APU channels
    lda #$00
    sta $4010           ; disable DMC IRQ

    bit PPUSTATUS       ; clear any pending vblank
:   bit PPUSTATUS       ; wait for first vblank (PPU warm-up)
    bpl :-

    ; Clear all 2KB of internal RAM. Shadow OAM ($0200) is set to $FF so any
    ; unused sprite sits off-screen below the visible area.
    lda #$00
    ldx #$00
@clrmem:
    sta $0000,x
    sta $0100,x
    sta $0300,x
    sta $0400,x
    sta $0500,x
    sta $0600,x
    sta $0700,x
    lda #$FF
    sta $0200,x         ; OAM page -> off-screen
    lda #$00
    inx
    bne @clrmem

:   bit PPUSTATUS       ; wait for second vblank; PPU is now ready
    bpl :-

    ; Rendering is still off here, so direct VRAM writes are safe.
    jsr LoadPalette
    jsr ClearNametable

    ; Enable NMI; background pattern table 0, sprite pattern table 0.
    lda #%10000000
    sta PPUCTRL
    ; Show background (and its leftmost 8px). Sprites stay off until we have a
    ; hero to draw; OAM DMA still runs harmlessly each frame.
    lda #%00001010
    sta PPUMASK

    ; fall through into the main loop
.endproc

; ----------------------------------------------------------------------------
; MAIN — game logic thread. No PPU access here; ever.
; ----------------------------------------------------------------------------
.proc MAIN
@loop:
    jsr WaitFrame
    ; ---- game logic goes here (none yet for Step 1: Boot) ----
    jmp @loop
.endproc

; Block until the NMI handler has run (one frame elapsed).
.proc WaitFrame
    lda frame_count
:   cmp frame_count
    beq :-
    rts
.endproc

; ----------------------------------------------------------------------------
; NMI — the only place PPU registers are written during the frame.
; ----------------------------------------------------------------------------
.proc NMI
    pha
    txa
    pha
    tya
    pha

    ; OAM DMA: copy shadow OAM ($0200) to the PPU.
    lda #$00
    sta OAMADDR
    lda #>OAM_BUF
    sta OAMDMA

    ; Flush the VRAM buffer here in a later step; nothing buffered yet.

    ; Reset scroll after any potential $2006 write this frame.
    bit PPUSTATUS
    lda #$00
    sta PPUSCROLL
    sta PPUSCROLL
    lda #%10000000
    sta PPUCTRL

    jsr SoundTick       ; called every frame, including lag frames (stub)

    inc frame_count

    pla
    tay
    pla
    tax
    pla
    rti
.endproc

.proc IRQ
    rti
.endproc

; ----------------------------------------------------------------------------
; Sound tick — stubbed for the slice; the call site is what matters.
; ----------------------------------------------------------------------------
.proc SoundTick
    rts
.endproc

; ----------------------------------------------------------------------------
; LoadPalette — write all 32 palette entries (rendering must be off).
; ----------------------------------------------------------------------------
.proc LoadPalette
    bit PPUSTATUS
    lda #$3F
    sta PPUADDR
    lda #$00
    sta PPUADDR
    ldx #$00
:   lda palette,x
    sta PPUDATA
    inx
    cpx #32
    bne :-
    rts
.endproc

; ----------------------------------------------------------------------------
; ClearNametable — fill nametable 0 ($2000) with tile 0 and palette 0, giving
; a solid backdrop-colored screen (tile 0 in CHR is all zeros = color 0).
; ----------------------------------------------------------------------------
.proc ClearNametable
    bit PPUSTATUS
    lda #$20
    sta PPUADDR
    lda #$00
    sta PPUADDR
    lda #$00
    ldx #$04            ; 4 x 256 = 1024 bytes (960 tiles + 64 attr)
    ldy #$00
:   sta PPUDATA
    iny
    bne :-
    dex
    bne :-
    rts
.endproc

; ----------------------------------------------------------------------------
; Palette data. Only $3F00 (universal backdrop) is visible for the solid
; screen; the rest are seeded so later steps have sane defaults.
; ----------------------------------------------------------------------------
.segment "RODATA"
palette:
    ; Background palettes
    .byte $21, $0F, $10, $30   ; backdrop = $21 (light blue) -> solid screen
    .byte $21, $06, $16, $30
    .byte $21, $09, $19, $30
    .byte $21, $01, $11, $30
    ; Sprite palettes
    .byte $21, $0F, $16, $30
    .byte $21, $0F, $11, $30
    .byte $21, $0F, $19, $30
    .byte $21, $0F, $30, $0F

; ----------------------------------------------------------------------------
; Interrupt vectors
; ----------------------------------------------------------------------------
.segment "VECTORS"
    .word NMI
    .word RESET
    .word IRQ

; ----------------------------------------------------------------------------
; CHR-ROM — 8KB, all zeros for now (tile 0 = solid color 0). Real tiles arrive
; in Step 2.
; ----------------------------------------------------------------------------
.segment "CHARS"
    .res $2000, $00
