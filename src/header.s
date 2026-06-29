; header.s — iNES header. NROM (mapper 0), 32KB PRG, 8KB CHR, vertical mirror.

.segment "HEADER"
    .byte "NES", $1A   ; magic
    .byte $02          ; PRG-ROM: 2 x 16KB = 32KB
    .byte $01          ; CHR-ROM: 1 x 8KB
    .byte $01          ; flags6: mapper low nibble = 0, vertical mirroring
                       ;   (two side-by-side nametables for horizontal scroll)
    .byte $00          ; flags7: mapper high nibble = 0
    .byte $00,$00,$00,$00,$00,$00,$00,$00  ; padding
