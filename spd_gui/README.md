# MabuieTool_SPD

Interface gráfica em Python/PySide6 para fazer **dump (backup) de firmware**
de feature phones com chipset **Spreadtrum/Unisoc** (SC6530, SC6531DA,
SC6531E) e suporte inicial a chips 4G (UMS9117 / T117 / T107 / T127).

É uma reimplementação, em Python, do protocolo usado pela ferramenta em C
`spd_dump` (projeto open-source `spreadtrum_flash` de Ilya Kurdyukov), com
interface gráfica no estilo de boxes profissionais (Infinity/Hydra).

📄 Se você quer só o passo a passo direto (instalar, conectar, fazer dump
ou gravar), veja **`guia.txt`** - este README traz mais contexto/detalhes.

⚠️ **USE POR SUA CONTA E RISCO.** Operações em bootloader podem, em teoria,
deixar um aparelho inutilizável se usadas incorretamente (endereços errados,
FDL incompatível, gravação do arquivo errado, etc.). A leitura/backup é
segura na grande maioria dos casos; **a gravação (aba "Gravar firmware") é
uma operação de risco real** - leia os avisos na própria interface.

## O que já funciona

- **Suporte a MediaTek (MT6260/MT6261)** - aba própria "MediaTek (MTK)",
  protocolo separado (`mtk_protocol.py`, porta do projeto
  `mediatek_flash` do mesmo autor do `spreadtrum_flash`): conectar
  (handshake BROM), carregar um payload/DA (equivalente ao FDL), ler
  JEDEC ID, MEID, dump/gravação/apagamento de flash. Veja
  `mtk_payload_src/LEIA-ME.md` para compilar o payload.

- Duas formas de conectar ao telefone:
  - **USB/libusb** (requer driver WinUSB/libusbK instalado via Zadig).
  - **Porta COM/serial**, reaproveitando um driver de fabricante que já
    exponha o telefone como porta COM - **sem precisar do Zadig**.
- Detecção automática da chegada do telefone em modo boot (USB `1782:4d00`).
- Carregamento do estágio FDL1 (handshake completo: check-baud, CRC16,
  connect, envio do binário, execução, troca para modo checksum).
- Identificação do chipset a partir do CHIP ID reportado pelo FDL1
  (SC6530/SC6531/SC6531E/UMS9117).
- Leitura/backup completo da flash (`read_flash`), com barra de progresso e
  log detalhado.
- Detecção automática de tamanho da partição via cabeçalho DHTB/VNTS (usado
  nos chips 4G).
- **Gravação de firmware** (`write_flash`) - grava um dump (ou outro
  arquivo `.bin`) de volta no telefone, no endereço detectado
  automaticamente pelo chipset (ou informado manualmente).
- **Apagar flash antes de gravar** (`erase_flash`), opcional.
- Proteção `CHECK_SECURE` (igual ao `spd_dump` original): recusa gravar ou
  apagar muito perto do início da área de firmware quando o telefone
  reporta secure boot ativo, para reduzir o risco de brick permanente.
- Carregamento opcional de um segundo estágio (FDL2), necessário para
  smartphones e para os 4G T117/T107/T127.
- `keep_charge` (manter carregando) e `power_off` (desligar ao final).
- Aba **"Utilitários"**: entrar em modo diagnóstico/download (conecta e
  carrega o FDL1 sem ler/gravar nada - útil para testar a conexão),
  reiniciar o telefone (`normal_reset`), e hard reset (apaga os dados de
  usuário/restaura padrões de fábrica via `erase_flash` numa região
  lógica de dados - `ERASE_UDISK`/`UDISK_IMG`).
- **Detecção automática de porta COM**: botão "Detectar automaticamente"
  ao lado da porta COM testa cada porta disponível com um handshake real
  (não só adivinha pelo VID/PID do driver) - útil quando o driver não
  preserva o identificador original do telefone.
- **Leitura do JEDEC ID da flash** (fabricante, tipo, capacidade) -
  ⚠️ requer recompilar o FDL1 com a extensão incluída em
  `custom_fdl_patch/` (não é parte do protocolo oficial - ver seção
  própria abaixo). Sem esse FDL1 recompilado, a ferramenta simplesmente
  avisa que o comando não é suportado, sem quebrar nada.
- **Tamanho de leitura automático pelo JEDEC ID** (aba "Ler / Fazer
  dump", modo de tamanho "Automático (JEDEC ID)") - detecta a capacidade
  real do chip e lê o chip inteiro, em vez de depender de um tamanho
  fixo digitado à mão. Também requer o FDL1 com o patch do JEDEC ID.
- Aba **"Extrair FDL2 (.pac)"**: lê o diretório de um firmware `.pac`
  oficial da Spreadtrum/Unisoc (reimplementação em Python do `unpac.c` do
  projeto original) e extrai qualquer arquivo dele - com botões dedicados
  "Extrair e usar como FDL1/FDL2" que já preenchem automaticamente o
  caminho **e o endereço de carga** nos campos da seção FDL (o endereço
  vem embutido no próprio `.pac`, no campo `addr` de cada entrada - não
  precisa adivinhar). Entradas do tipo `0x101` são marcadas como `[FDL]`
  na lista. Não precisa do telefone conectado - é só leitura local do
  arquivo `.pac` (que você precisa obter separadamente, ex.: do site do
  fabricante do seu aparelho).
- Aba **"Partições (FDL2)"**: lista as partições reportadas pelo telefone
  (`BSL_CMD_READ_PARTITION`), lê o conteúdo de uma partição por nome
  (`BSL_CMD_READ_START`/`READ_MIDST`/`READ_END`), e **apaga uma partição
  pelo nome** (`erase_partition` - mesmo `BSL_CMD_ERASE_FLASH`, mas com
  payload de nome de partição em vez de endereço bruto) - ex.: `boot`,
  `recovery`, `userdata`. Apagar por nome é a versão **precisa** de
  "restaurar definições de fábrica": o FDL2 sabe o tamanho certo da
  partição sozinho, em vez de você ter que estimar um intervalo de
  endereços (que é o que a opção "Hard reset" da aba Utilitários faz,
  para quando só se tem o FDL1 custom). **Só funciona com o FDL2 oficial
  do fabricante** carregado como segundo estágio; o FDL1 custom deste
  projeto não implementa esses comandos (confirmado no código-fonte do
  `custom_fdl` - só trata `CONNECT`/`START_DATA`/`MIDST_DATA`/
  `END_DATA`/`EXEC_DATA`/`CHANGE_BAUD`/`READ_FLASH`/`ERASE_FLASH`/
  `OFF_CHG`).

## O que ainda não está implementado (próximos passos)

- Gravação/leitura por nome de partição (`write_part`/`read_part`,
  específico do fluxo de smartphones com tabela de partições).
- Leitura/gravação de itens de NV.
- Lista de partições em XML para smartphones (`partition_list`).
- Leitura de UID / eFuse.

A camada de protocolo (`spd_protocol.py`) já expõe os comandos BSL
necessários, então essas funções podem ser adicionadas seguindo o mesmo
padrão de `read_flash`/`write_flash`.

## Sobre o modo "Porta COM" (sem trocar o driver)

O dispositivo Spreadtrum em modo boot (`1782:4d00`) só funciona no Windows
se houver ALGUM driver associado a ele - não existe como evitar instalar
algum driver, isso é uma exigência do próprio Windows para qualquer
dispositivo USB de fabricante. A diferença é qual driver:

- Se você (ou uma assistência técnica) **já instalou** o driver oficial da
  Spreadtrum/do fabricante do telefone em algum momento (comum em PCs de
  loja de conserto - normalmente chamado de algo como "Spreadtrum U2S
  Diag" ou similar), esse driver já expõe o telefone como uma **porta
  COM** comum. Nesse caso, use o modo "Porta COM" na interface e **não
  precisa mexer em mais nada**.
- Se o dispositivo aparece como "Desconhecido" no Gerenciador de
  Dispositivos (nenhum driver instalado), alguém precisa instalar um
  driver - e o Zadig (modo "USB") é a forma mais simples e gratuita de
  fazer isso sem precisar de um instalador assinado digitalmente.

Ou seja: o modo Porta COM não elimina a necessidade de driver, só evita
precisar rodar o Zadig **se você já tiver esse driver instalado**.

## Como adicionar suporte a outro chipset SPD

A identificação de chipset não fica mais fixa no código - fica em
**`chips.json`**, na raiz do projeto. Cada entrada tem esta cara:

```json
{
  "name": "Nome amigável do chipset",
  "id_xor": "0x65300000",
  "id_shift": 17,
  "fw_addr": "0x30000000",
  "ram_addr": "0x30000000",
  "fdl1_addr": "0x40004000",
  "notes": "observações"
}
```

O casamento usa a mesma lógica do `spd_dump.c` original:
`(chip_id ^ id_xor) >> id_shift == 0`. `fw_addr` é o endereço usado para
gravação (aba "Gravar firmware"); `fdl1_addr` é só uma sugestão exibida
na interface. Use `null` para valores que você ainda não souber.

**O que é preciso para adicionar um chipset novo de verdade** (isto não é
algo que dá pra inventar/adivinhar - precisa de dados reais do chip):

1. **Um FDL1 que rode nesse chip específico.** Para SC6530/SC6531DA/
   SC6531E, o projeto original já traz o código-fonte em `custom_fdl/`
   (você compila com um toolchain ARM). Para outros chips (ex.: linha
   SC77xx/SC98xx, de smartphone), normalmente não existe um FDL1
   "custom" pronto - a alternativa costuma ser extrair o `fdl1-sign.bin`
   e o `fdl.bin` de dentro do firmware oficial do aparelho (arquivo
   `.pac`) usando a ferramenta oficial da Spreadtrum ("Research
   Download"/"SPD Tool"), e usar o endereço de carga que vem no XML de
   partições desse firmware.
2. **Descobrir o CHIP ID real.** Só dá pra saber depois de já ter um
   FDL1 que funcione nesse chip: conecte, carregue esse FDL1 pela
   interface e veja no log a linha `BSL_REP_VER (FDL1): ...CHIP ID =
   0x...`. Esse valor (ou um padrão que cubra a família dele) vira o
   `id_xor`/`id_shift` da nova entrada.
3. **(Opcional, só se quiser gravar) o `fw_addr` correto** - normalmente
   o mesmo endereço-base de RAM/flash mapeada usado para carregar o
   FDL2 nesse chip.

Depois de ter esses dados, é só acrescentar a entrada em `chips.json` -
não precisa mexer em `spd_protocol.py`. Também dá pra usar a ferramenta
hoje com um chipset "desconhecido": a interface deixa preencher o
endereço do FDL1 e (na aba de gravação) o endereço de escrita
manualmente mesmo sem uma entrada em `chips.json` - só não vai aparecer
o nome do chipset identificado no log.

## Notas técnicas importantes (bugs corrigidos com hardware real)

Testando num SC6531E real, dois problemas apareceram e foram corrigidos:

**1. Endereço de gravação/apagamento errado.** O comentário no topo do
`spd_cmd.h` original documenta os endereços de carga do FDL2 **oficial**
do fabricante (`0x34000000`/`0x14000000`, tirados de arquivos `.xml` do
firmware). Eu tinha usado esses valores como `fw_addr` no `chips.json`.
Só que o FDL1 **custom** deste projeto (`custom_fdl/main.c`) usa
internamente um endereço-base *diferente* para decidir se uma
escrita/apagamento vai para a flash SPI-NOR de verdade: a macro
`FW_ADDR`, que vale `0x30000000` (SC6530/SC6531DA) ou `0x10000000`
(SC6531E) - **sem** o offset de `0x04000000` da documentação do FDL2.
Fora dessa janela de 16 MB ao redor do `FW_ADDR` real, uma gravação vira
um `memcpy` comum em RAM (não persiste) e um apagamento é rejeitado pelo
telefone (`BSL_REP_INVALID_CMD`, código `0x82`). Já corrigi o
`chips.json` para os valores certos, e adicionei uma checagem
(`check_custom_fdl_window`) que agora recusa a operação com uma mensagem
clara em vez de deixar o telefone responder com um código de erro cru -
mas só quando o FDL2 oficial (segundo estágio) **não** está marcado,
já que essa checagem só vale para o FDL1 custom.

**2. Modo Porta COM extremamente lento.** A causa não era (só) a taxa de
baud: a forma como eu configurava o timeout de leitura no `pyserial`
fazia cada bloco que não enchesse o buffer de leitura inteiro **esperar
até 1 segundo cheio antes de retornar**, mesmo com os dados já
disponíveis - no Windows, uma leitura com timeout fixo espera o buffer
encher OU o timeout completo esgotar, o que vier primeiro, mesmo se só
faltarem alguns bytes do fim de uma mensagem. Como isso acontecia pelo
menos uma vez por bloco lido, num dump de 4 MB isso sozinho podia somar
minutos de espera morta. Troquei por um esquema de *polling* com
intervalo curto (20 ms): assim que o primeiro byte chega, o resto que já
estiver no buffer do sistema é lido na hora, sem esperar o timeout
inteiro. Também aumentei o tamanho de bloco padrão (dump e gravação) e
deixei o baud rate mais alto (`921600`) como padrão.

**3. Timeout curto demais para apagar flash.** Depois de corrigir o
endereço, o apagamento passou a ser aceito pelo telefone - mas
`erase_flash` usava o mesmo timeout curto (1 segundo) das outras
operações, enquanto apagar setores de flash NOR é uma operação de
hardware bloqueante que pode legitimamente levar dezenas de segundos a
minutos, sem nenhuma resposta parcial nesse meio tempo. O cliente
desistia antes do telefone terminar. Agora `erase_flash` usa um timeout
calculado a partir do tamanho a apagar (folga de ~500ms por bloco de 4KB
+ margem base), e a interface mostra uma barra de progresso
indeterminada com um aviso de que pode demorar em vez de parecer travada.

## Sobre a leitura do JEDEC ID (extensão não-oficial)

O protocolo original (`spd_dump`/`custom_fdl`) **não tem** um comando
para devolver o JEDEC ID da flash ao PC - o firmware lê esse ID
internamente (`sfc_readid()`), mas só usa para decidir bits de proteção
de escrita, nunca reporta de volta. Para expor isso na ferramenta, criei
uma pequena extensão não-oficial: `custom_fdl_patch/` é uma cópia do
`custom_fdl` original com um único comando novo adicionado
(`0x50`), que devolve o JEDEC ID lido.

**Isso exige recompilar o FDL1** com um toolchain ARM - exatamente os
mesmos passos de compilar o `custom_fdl` original (veja
`custom_fdl_patch/README_PATCH_JEDEC.md`), só que a partir dessa pasta
com o patch já aplicado. Se você não tiver como recompilar, sem problema:
a ferramenta detecta que o comando não é suportado e simplesmente avisa
no log, sem quebrar nenhuma outra função.

## Sobre funções de IMEI

Decidi **não** incluir uma função de "reparo"/edição de IMEI nesta
ferramenta. O motivo: tecnicamente, "reparar IMEI" e "clonar/trocar
IMEI" usam exatamente o mesmo mecanismo (escrever um valor de IMEI
arbitrário na área de NV) - o software não tem como saber se o valor
sendo gravado é legitimamente o IMEI original daquele aparelho ou um
IMEI de outro telefone (usado pra reativar aparelho roubado/bloqueado
ou burlar operadora), então não dá pra construir isso de um jeito que só
funcione pro caso legítimo.

O que já é possível hoje, com as abas genéricas de Leitura/Gravação, e
cobre o caso de reparo legítimo mais comum (NV corrompida no MESMO
aparelho): fazer backup da região `NV (0x90000001)` pela aba de leitura
*antes* de mexer no telefone, e restaurar esse mesmo backup depois pela
aba de gravação, informando o endereço correto de NV, caso algo dê
errado. Isso não expõe nem edita o valor do IMEI diretamente - só
restaura o bloco de NV inteiro, exatamente como estava.

## Instalação (Windows)

1. Instale o **Python 3.10+** (marque "Add to PATH" no instalador).
2. Driver: **teste primeiro o modo "Porta COM"** (passo 4 abaixo) - se o
   telefone já aparecer como porta COM no Gerenciador de Dispositivos ao
   conectar em modo boot, você pode pular este passo inteiro. Caso
   contrário, instale o **driver WinUSB/libusbK** usando o
   [Zadig](https://zadig.akeo.ie/):
   - Conecte o telefone segurando a tecla de boot (veja abaixo).
   - Abra o Zadig, marque "List All Devices", localize o dispositivo
     `1782:4d00` (pode aparecer como "SPRD U2S Diag" ou similar).
   - Selecione o driver **WinUSB** e clique em "Install Driver".
3. Abra um terminal na pasta do projeto e instale as dependências:
   ```
   pip install -r requirements.txt
   ```
4. Obtenha um `nor_fdl1.bin` (veja `fdl_files/LEIA-ME.txt`) e coloque-o em
   `fdl_files/`.
5. Rode a aplicação:
   ```
   python main.py
   ```

## Como encontrar a tecla de boot do seu aparelho

Remova a bateria, espere uns 5 segundos, recoloque. Conecte o cabo USB
segurando uma tecla (centro, tecla de chamada, `*`, `0`, `9`... varia por
modelo, às vezes é uma combinação de duas teclas). Se a tecla certa estiver
pressionada, o Windows deve reconhecer brevemente o dispositivo
`1782:4d00` antes de entrar em modo de carregamento. Alternativamente, use
um cabo "boot" com os pinos 4 e 5 (D+/D-) em curto — equivalente a um
adaptador OTG + cabo AM-AM.

## Uso básico na interface - leitura (dump)

1. Escolha o modo de conexão (USB ou Porta COM) e, se for COM, a porta.
2. Selecione o arquivo **FDL1** e confira o endereço de carga
   (`0x40004000` funciona para SC6530/SC6531DA/SC6531E com o FDL1
   "custom").
3. Na aba "Ler / Fazer dump", escolha a região a ler (o padrão
   `PS (0x80000003)` cobre a flash inteira na maioria dos feature phones)
   e o tamanho (ex.: `0x400000` para 4 MB, tamanho mais comum nesses
   aparelhos).
4. Escolha onde salvar o arquivo `.bin`.
5. Clique em **"Aguardar telefone e iniciar dump"** e só então conecte o
   aparelho segurando a tecla de boot.
6. Acompanhe o progresso e o log. Ao final, o arquivo estará salvo no
   caminho escolhido.

Para telefones 4G (T117/T107/T127) ou smartphones, marque "Carregar um
segundo estágio (FDL2)" e informe o FDL2 e o endereço de carga corretos
para o seu modelo (normalmente extraídos do firmware original).

## Uso básico na interface - gravação (flash)

1. Nos mesmos passos 1-2 acima (conexão + FDL1).
2. Na aba "Gravar firmware (flash)", selecione o arquivo `.bin` a gravar
   (normalmente um dump feito anteriormente com esta mesma ferramenta,
   *no mesmo aparelho/modelo*).
3. Deixe "Endereço de gravação" em branco para usar o endereço detectado
   automaticamente pelo chipset (`fw_addr`: `0x30000000` para
   SC6530/SC6531DA, `0x10000000` para SC6531E - ver ressalva importante
   abaixo), ou informe manualmente.
4. Marque "Entendo os riscos..." e clique em
   **"Aguardar telefone e gravar firmware"**, confirme o aviso e conecte
   o telefone.
5. Não desconecte o cabo nem desligue o PC até o log indicar
   "Gravação concluída".

A gravação usa exatamente o mesmo mecanismo do `write_data` do
`spd_dump` original: os dados são escritos como se fossem memória RAM,
mas nesse endereço a flash NOR está mapeada, então a gravação vai
diretamente para a flash. Por isso ela é simétrica à leitura pela região
`PS (0x80000003)`: um dump feito com o tamanho certo pode ser regravado
sem alterações.

## Uso básico na interface - utilitários (diag / reset / hard reset)

Nos mesmos passos 1-2 de conexão + FDL1, a aba "Utilitários" oferece três
ações rápidas (sem precisar preencher região/tamanho de dump):

- **Modo diagnóstico**: só conecta, carrega o FDL1 e mostra o chipset
  identificado - não lê nem grava nada. Bom para testar se o driver, o
  cabo e o FDL1 estão certos antes de partir para um dump de verdade.
- **Reiniciar telefone**: envia o comando de reinício normal do BSL.
- **Hard reset**: apaga uma região lógica de dados de usuário
  (`ERASE_UDISK`/`UDISK_IMG`) via `erase_flash`, sem tocar no firmware.
  ⚠️ O comportamento exato dessas duas regiões "mágicas" (elas usam um ID
  lógico, não um endereço físico de memória) não é totalmente documentado
  no projeto original e **eu não pude validar em hardware real** - o
  tamanho informado pode ser ignorado pelo FDL dependendo do chipset.
  Recomendo fortemente fazer um dump de backup completo antes (aba "Ler /
  Fazer dump") e testar o hard reset num aparelho de baixo risco primeiro.

## Uso básico na interface - partições (FDL2 oficial)

Requer o FDL2 oficial do fabricante marcado e carregado (seção FDL, "Carregar
um segundo estágio"). Com o FDL1 custom sozinho, os botões desta aba vão
falhar com "resposta inesperada" - isso é esperado, não é bug.

1. Clique em "Aguardar telefone e listar partições" para ver os nomes e
   tamanhos reportados pelo telefone.
2. Escolha uma partição na lista (preenche o nome e sugere o tamanho
   automaticamente) ou digite o nome manualmente.
3. Ajuste o deslocamento/tamanho se quiser ler só uma parte, escolha onde
   salvar, e clique em "Aguardar telefone e ler partição".

## Gerando um .exe standalone (PyInstaller)

```
pip install pyinstaller
pyinstaller --noconsole --onefile --name MabuieTool_SPD main.py
```

O executável ficará em `dist/MabuieTool_SPD.exe`. Copie a pasta `fdl_files/`
para perto do `.exe` se quiser distribuí-la junto.

## Estrutura do projeto

```
spd_protocol.py   # camada de protocolo (framing HDLC, checksum, comandos BSL,
                   # transporte USB e Serial/COM, leitura e gravação)
spd_pac.py        # leitura/extração de firmwares .pac (FDL1/FDL2 oficiais)
chips.json        # base de dados de chipsets (editável, sem precisar mexer no código)
gui.py            # interface gráfica PySide6 + threads de trabalho
main.py           # ponto de entrada
guia.txt          # passo a passo direto (instalar, conectar, dump, gravar)
test_protocol_offline.py  # testes do framing/checksum sem hardware
test_pac_offline.py       # testes de leitura/extração de .pac sem hardware
fdl_files/        # onde colocar os binários FDL
custom_fdl_patch/ # código-fonte do FDL1 custom + patch do JEDEC ID (opcional, requer recompilar)
mtk_protocol.py   # protocolo MediaTek (BROM + payload custom) - MT6260/MT6261
mtk_payload_src/  # código-fonte original do payload/DA MTK (opcional, requer compilar)
test_mtk_offline.py       # testes do protocolo MTK sem hardware
```

## Créditos

Protocolo baseado no código-fonte de `spreadtrum_flash`
(https://github.com/ilyakurdyukov/spreadtrum_flash), licença conforme o
projeto original ("AS IS", sem garantias).
