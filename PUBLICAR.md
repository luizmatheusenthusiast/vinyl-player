# Como publicar para Windows e Linux (sem instalar nada no seu computador)

A ideia: você guarda o projeto no **GitHub** (grátis). Quando você cria uma "versão", o próprio GitHub
gera os instaladores — o **.exe para Windows** e o **.deb para Ubuntu** — e deixa tudo numa página de
download. Quem usa Windows só entra na página, baixa o `Vinyl-Player-Setup-….exe`, dá dois cliques e pronto.

## O jeito mais fácil (Ubuntu): um comando

Extraia o zip, abra o terminal na pasta `vinyl-player` (clique direito → "Abrir no terminal") e rode:

```bash
bash enviar_para_github.sh
```

Ele instala o que faltar, pede o login no GitHub pelo navegador, cria o repositório `vinyl-player`,
envia tudo e já publica a versão. Depois é só esperar uns 10 minutos e pegar os instaladores na aba **Releases**.
(Para uma versão nova: mude `version.py` e rode o mesmo comando de novo.)

## Passo a passo manual (uma vez só)

1. Crie uma conta grátis em <https://github.com> e clique em **New repository**.
   Nome: `vinyl-player`. Deixe **Public** (o download fica aberto para qualquer pessoa) e crie.
2. Na página do repositório, clique em **uploading an existing file** e arraste **todo o conteúdo**
   da pasta `vinyl-player` (incluindo a pasta escondida `.github`; se o seu sistema não mostrar,
   use o Git: `git init`, `git add .`, `git commit -m "primeira versão"`, `git push`).
   Clique em **Commit changes**.
3. Vá em **Releases → Create a new release**. Em **Choose a tag**, digite `v1.1.0` e clique em
   **Create new tag**. Dê o título "Vinyl Player 1.1.0" e clique em **Publish release**.
4. Abra a aba **Actions**: vai aparecer "Criar instaladores" rodando (leva uns 10 minutos).
   Quando ficar verde, volte em **Releases**: os arquivos estarão anexados à versão.

## O que as pessoas baixam

| Sistema | Arquivo | Como usar |
|---|---|---|
| Windows | `Vinyl-Player-Setup-1.1.0.exe` | Dois cliques → Avançar → Concluir |
| Windows (sem instalar) | `Vinyl-Player-Portatil-1.1.0.zip` | Extrair e abrir `Vinyl Player.exe` |
| Ubuntu / Debian | `vinyl-player_1.1.0_amd64.deb` | Dois cliques → Instalar |

Mande às pessoas o link da página **Releases** do seu repositório
(`https://github.com/SEU-USUARIO/vinyl-player/releases/latest`).

> No Windows pode aparecer "O Windows protegeu seu PC": **Mais informações → Executar assim mesmo**.
> Isso acontece com qualquer programa sem assinatura digital paga (cerca de US$ 100–300 por ano);
> não significa que o programa seja perigoso.

## Lançar uma versão nova depois

1. Mude o número em `version.py` (por exemplo `1.2.0`) e envie a alteração ao GitHub.
2. Crie uma nova release com a tag `v1.2.0`. Os instaladores novos são gerados sozinhos.

## Prefere gerar no seu computador?

- Windows: `build_windows.bat` (dois cliques). Ubuntu: `bash build_linux.sh`.
- Para testar o processo do GitHub sem publicar nada: aba **Actions → Criar instaladores → Run workflow**.
  Os arquivos ficam em "Artifacts" no fim da execução.

---

# Instalar no Linux e publicar nas lojas

## Instalar no Ubuntu (quem recebe o programa)

- **Pelo `.deb`** (da página Releases): dois cliques no arquivo → **Instalar**. Ou no terminal:
  `sudo apt install ./vinyl-player_1.1.0_amd64.deb`. Depois procure **Vinyl Player** no menu de aplicativos.
- Para **desinstalar**: `sudo apt remove vinyl-player` (ou pela Central de Programas).
- Para **atualizar**: baixe o `.deb` novo e instale por cima.

## Publicar em lojas (Flathub / Snap Store)

Primeiro publique no GitHub (acima): as lojas exigem um endereço público do código e de uma versão.
Depois disso há dois caminhos gratuitos:

### Flathub (a loja do GNOME Software, serve para Ubuntu, Fedora, etc.)
1. Escolha um ID único, por exemplo `io.github.SEU-USUARIO.VinylPlayer`.
2. Crie 3 arquivos: o **manifesto** (`.yml`, diz como construir o programa — para PySide6 usa-se a base
   `io.qt.PySide.BaseApp`), o **arquivo `.desktop`** e o **`.metainfo.xml`** (descrição, capturas de tela,
   licença e versões que aparecem na loja).
3. Teste localmente com `flatpak-builder`.
4. Abra um *pull request* em <https://github.com/flathub/flathub> seguindo
   <https://docs.flathub.org/docs/for-app-authors/submission>. Pessoas voluntárias revisam; ao aprovar,
   o app aparece na loja e é atualizado a cada nova versão.
- O Flathub exige **licença de código aberto** (por exemplo MIT) e construção **sem internet**: todas as
  dependências Python (PySide6, mutagen) precisam ser listadas no manifesto.

### Snap Store (a loja padrão do "Ubuntu Software")
1. Crie uma conta grátis em <https://snapcraft.io>.
2. Escreva um `snapcraft.yaml` (receita de construção) e rode `snapcraft`; registre o nome com
   `snapcraft register vinyl-player` e envie com `snapcraft upload`.
3. Peça a publicação no canal **stable**. Apps simples costumam ser aprovados rápido.

Em ambos os casos, o `.exe` do Windows continua sendo distribuído pelo GitHub (ou pela Microsoft Store,
que exige conta de desenvolvedor paga).
