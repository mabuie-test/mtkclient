# Payload/DA MediaTek (MT6260/MT6261)

Esta pasta é uma cópia do código-fonte original do projeto
`mediatek_flash` (mesmo autor do `spreadtrum_flash`), incluída aqui só
para referência e para compilar o **payload/DA** usado pela aba
"MediaTek (MTK)" do MabuiETool SPD.

## O que é o payload/DA

Equivalente ao FDL do lado Spreadtrum: um código pequeno que a
ferramenta carrega na RAM do telefone (via `simple_da` / `send_da` +
`jump_da`) e que passa a responder aos comandos de leitura/gravação/
apagamento da flash (JEDEC ID, `read_flash`, `write_flash`,
`erase_flash`). **Sem esse payload carregado**, só os comandos básicos
do BROM funcionam (conectar, ler versão, ler memória RAM diretamente) -
a aba MTK já trata esse caso e avisa no log em vez de travar.

## Como compilar

Precisa do Android NDK (traz um compilador ARM funcional):

1. Baixe em https://developer.android.com/ndk/downloads
2. Dentro de `payload/`, veja o `README.md` e o `Makefile` dessa pasta
   para o comando exato (usa `clang` do NDK visando ARM).
3. O resultado é o binário do payload - use esse arquivo no campo
   "Arquivo do payload" da aba MTK, com o endereço de carga
   `0x70008000` (padrão já preenchido na interface).

## mtk_dump.c (ferramenta original em C)

Não precisa compilar isso - o `mtk_protocol.py` na raiz do
MabuiETool SPD já é uma reimplementação completa em Python do que esse
`mtk_dump.c` faz (handshake BROM, envio de DA, comandos SFI de flash).
Mantido aqui só para referência/comparação, caso precise conferir algum
detalhe do protocolo original.
