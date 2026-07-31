; iNES header — MMC3 (mapper 4), 256KB PRG, 128KB CHR, battery-backed PRG-RAM.
.segment "HEADER"
    .byte $4E, $45, $53, $1A   ; "NES", EOF
    .byte 16                   ; PRG-ROM: 16 x 16KB = 256KB
    .byte 16                   ; CHR-ROM: 16 x  8KB = 128KB
    .byte $43                  ; flags6: mapper low nibble 4, battery, vertical
    .byte $00                  ; flags7: mapper high nibble 0 (iNES 1.0)
    .byte $01                  ; flags8: PRG-RAM 8KB
    .byte $00, $00, $00, $00, $00, $00, $00
