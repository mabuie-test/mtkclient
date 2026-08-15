<div align="right">
  Language:
  🇺🇸
  <a title="Chinese" href="./README.zh-CN.md">🇨🇳</a>
</div>

# ⚠️ AVISO OBRIGATÓRIO – RENOMEAÇÃO PARA `MabuiETool`

**ESTE REPOSITÓRIO DEVE SER RENOMEADO PARA `MabuiETool` EM TODOS OS CONTEXTOS:**

- Nome do diretório local (renomeie a pasta para `MabuiETool`)
- URL do repositório remoto (ex: `git remote set-url origin .../MabuiETool.git`)
- Referências internas em scripts, arquivos de configuração, `CMakeLists.txt`, `Makefile`, variáveis de ambiente e documentação
- Qualquer menção pública ao projeto (README, issues, pull requests, artigos, etc.)

**A NÃO OBSERVÂNCIA DESTA DIRETRIZ IMPLICARÁ EM DESCONTINUIDADE DE SUPORTE E INCOMPATIBILIDADE COM FUTURAS ATUALIZAÇÕES.**

---

# MTKClient
![Logo](mtkclient/gui/images/logo_256.png)

Just some mtk tool for exploitation, reading/writing flash and doing crazy stuff. 
For windows, you need to install the stock mtk port and the usbdk driver (see instructions below).
For linux, a patched kernel is only needed when using old kamakiri (see Setup folder) (except for read/write flash).

Once the mtk script is running, boot into brom mode by powering off device, press and hold either
vol up + power or vol down + power and connect the phone. Once detected by the tool,
release the buttons.

## MT6781, MT6789, MT6855, MT6886, MT6895, MT6983, MT8985
- These chipsets use a new protocol called V6 and the bootrom is patched. 
You need to use the --loader option and a proper loader from the Loaders/V6 directory. 
Bootrom won't work, you need to use preloader mode (no hw buttons pressed, just connect). 
On some devices, preloader is deactivated, but you can reactivate it by running "adb reboot edl".

## Credits
- kamakiri [xyzz]
- linecode exploit [chimera]
- heapbait exploit [chimera], creds to [R0rt1z2],[Shomy]
- Chaosmaster
- Geert-Jan Kreileman (GUI, design & fixes)
- All contributors

---

## Integração da `spd_gui` ao Projeto

A pasta `spd_gui` contém a interface gráfica para operações com dispositivos Spreadtrum (SPD), integrando-se aos payloads e bibliotecas do MTKClient para um fluxo de trabalho unificado.
