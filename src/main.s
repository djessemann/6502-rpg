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

.import fieldmap, fieldattr

; ----------------------------------------------------------------------------
; Zeropage variables
; ----------------------------------------------------------------------------
.segment "ZEROPAGE"
frame_count:  .res 1   ; incremented by NMI; main loop syncs against it
ptr:          .res 2   ; general 16-bit pointer (init-time use)

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
    jsr DrawField

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
; DrawField — copy the one-screen map (960 bytes) to nametable 0 ($2000) and
; the attribute table (64 bytes) to $23C0. Init-time only (rendering off).
; ----------------------------------------------------------------------------
.proc DrawField
    ; Nametable tiles: 960 bytes = 3 full pages + 192.
    bit PPUSTATUS
    lda #$20
    sta PPUADDR
    lda #$00
    sta PPUADDR

    lda #<fieldmap
    sta ptr
    lda #>fieldmap
    sta ptr+1

    ldx #$03            ; 3 full 256-byte pages
@page:
    ldy #$00
@byte:
    lda (ptr),y
    sta PPUDATA
    iny
    bne @byte
    inc ptr+1
    dex
    bne @page

    ldy #$00            ; remaining 192 bytes (ptr now at fieldmap+768)
@tail:
    lda (ptr),y
    sta PPUDATA
    iny
    cpy #192
    bne @tail

    ; Attribute table at $23C0: 64 bytes.
    lda #$23
    sta PPUADDR
    lda #$C0
    sta PPUADDR
    ldx #$00
@attr:
    lda fieldattr,x
    sta PPUDATA
    inx
    cpx #64
    bne @attr
    rts
.endproc

; ----------------------------------------------------------------------------
; Palette data. Only $3F00 (universal backdrop) is visible for the solid
; screen; the rest are seeded so later steps have sane defaults.
; ----------------------------------------------------------------------------
.segment "RODATA"
palette:
    ; Background palettes (2 used by the field):
    .byte $0F, $1A, $2A, $07   ; 0: ground  - greens + brown (grass/tree/path/wall)
    .byte $0F, $0C, $11, $21   ; 1: water   - teal/blue/light blue
    .byte $0F, $1A, $2A, $07   ; 2: spare (= ground)
    .byte $0F, $1A, $2A, $07   ; 3: spare (= ground)
    ; Sprite palettes (seeded for later steps):
    .byte $0F, $16, $27, $30
    .byte $0F, $0C, $11, $30
    .byte $0F, $1A, $2A, $30
    .byte $0F, $0F, $30, $0F

; ----------------------------------------------------------------------------
; Interrupt vectors
; ----------------------------------------------------------------------------
.segment "VECTORS"
    .word NMI
    .word RESET
    .word IRQ

; CHR-ROM tile data lives in chr.s (generated by tools/gen_assets.py).
