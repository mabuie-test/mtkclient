# Patch: leitura do JEDEC ID (extensão MabuieTool_SPD)

Esta pasta é uma cópia do `custom_fdl` original do projeto
`spreadtrum_flash`, com **uma única adição**: um novo comando
(`MABUIE_CMD_READ_JEDEC_ID`, opcode `0x50`) que devolve ao PC o JEDEC ID
da flash SPI-NOR (fabricante + tipo + capacidade), lido via
`sfc_readid()` - a mesma função que o firmware já usa internamente
(`sfc_unlock()`), só que agora reportada de volta em vez de ficar só
dentro do firmware.

**Isto NÃO é o protocolo oficial da Spreadtrum/Unisoc** - é uma extensão
específica desta ferramenta (MabuieTool_SPD). Um `nor_fdl1.bin` sem este
patch simplesmente vai responder "comando desconhecido" a esse comando -
sem problema nenhum, a ferramenta já trata esse caso e mostra uma
mensagem explicando que o FDL1 carregado não suporta a leitura do JEDEC
ID.

## O que mudou

Só o `main.c` foi alterado, em dois pontos:
1. `#define MABUIE_CMD_READ_JEDEC_ID 0x50` perto do topo.
2. Uma função `read_jedec_id()` e um novo `case` no despachante de
   comandos, dentro do `#if WITH_SFC` (mesmo bloco do `erase_flash`, já
   que precisa da mesma infraestrutura de acesso à flash SPI).

Nenhum outro arquivo foi tocado.

## Como compilar (Windows, via WSL - caminho mais simples)

1. Instale o WSL (se ainda não tiver): abra o PowerShell como
   administrador e rode `wsl --install`, reinicie se pedir, e crie um
   usuário Ubuntu quando abrir pela primeira vez.
2. Dentro do WSL (terminal Ubuntu), instale o compilador cruzado ARM:
   ```
   sudo apt-get update
   sudo apt-get install -y gcc-arm-linux-gnueabi make
   ```
3. Copie esta pasta (`custom_fdl_patch`) para dentro do WSL - o mais
   fácil é abrir o Explorador de Arquivos do Windows, digitar `\\wsl$`
   na barra de endereço, entrar na sua distro, e colar a pasta em algum
   lugar como `/home/SEU_USUARIO/custom_fdl_patch`. Ou, de dentro do
   WSL, copiar diretamente do Windows:
   ```
   cp -r /mnt/c/caminho/para/custom_fdl_patch ~/custom_fdl_patch
   cd ~/custom_fdl_patch
   ```
4. Compile:
   ```
   make all TOOLCHAIN=/usr/bin/arm-linux-gnueabi
   ```
   **Não precisa (e não deve) definir `CHIP=1`** - o padrão (`CHIP=0`)
   gera um binário único que detecta o chipset sozinho em tempo real
   (SC6530/SC6531DA/SC6531E), exatamente como o `nor_fdl1.bin` que você
   já está usando hoje.
5. O resultado é `nor_fdl1.bin` nesta mesma pasta. Copie esse arquivo
   para a pasta `fdl_files/` do MabuieTool_SPD (pode substituir o antigo
   ou usar um nome diferente, ex.: `nor_fdl1_jedec.bin`) e selecione-o
   na interface como de costume - endereço de carga continua
   `0x40004000`.

## Alternativa: Android NDK (sem WSL, direto no Windows)

Se preferir não usar WSL, o Android NDK moderno já traz um Clang que
roda nativamente no Windows:

1. Baixe o "NDK (standalone)" em https://developer.android.com/ndk/downloads
   e extraia (ex.: `C:\android-ndk-r26d`).
2. Abra o PowerShell na pasta `custom_fdl_patch` e rode (ajuste a versão
   da pasta/host conforme o que baixou):
   ```
   $NDK = "C:\android-ndk-r26d"
   $CLANG = "$NDK\toolchains\llvm\prebuilt\windows-x86_64\bin\armv7a-linux-androideabi21-clang.cmd"
   make all CC="$CLANG"
   ```
   (Precisa ter `make` disponível no Windows - mais simples instalar via
   `choco install make` ou usar o `mingw32-make` do MSYS2/MinGW.)

## Confirmando que funcionou

Depois de trocar o FDL1 pelo novo `nor_fdl1.bin`, use a aba
"Utilitários" -> "Entrar em modo diagnóstico" e veja se aparece no log
uma linha `JEDEC ID: 0x...` (em vez do aviso "este FDL1 não suporta a
leitura do JEDEC ID").
