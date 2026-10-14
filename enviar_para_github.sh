#!/usr/bin/env bash
# Envia o Vinyl Player para o GitHub e já publica a versão (os instaladores são criados sozinhos lá).
# Como usar (no terminal, dentro desta pasta):   bash enviar_para_github.sh
set -euo pipefail
cd "$(dirname "$0")"

VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' version.py)"

echo "== 1/4  Ferramentas (git e gh) =="
need=()
command -v git >/dev/null || need+=(git)
command -v gh  >/dev/null || need+=(gh)
if [ "${#need[@]}" -gt 0 ]; then
    echo "Vou instalar: ${need[*]} (pede sua senha)"
    sudo apt-get update && sudo apt-get install -y "${need[@]}"
fi

echo "== 2/4  Login no GitHub =="
if ! gh auth status >/dev/null 2>&1; then
    echo "Vai abrir um passo a passo: escolha GitHub.com > HTTPS > 'Login with a web browser',"
    echo "copie o código que aparecer e confirme no navegador."
    gh auth login
fi

echo "== 3/4  Enviando o projeto =="
[ -d .git ] || git init -b main
git add .
git -c user.name="$(gh api user --jq .login)" -c user.email="$(gh api user --jq '.id|tostring')+$(gh api user --jq .login)@users.noreply.github.com" \
    commit -m "Vinyl Player $VERSION" || echo "(nada novo para guardar)"
if ! git remote get-url origin >/dev/null 2>&1; then
    gh repo create vinyl-player --public --source=. --remote=origin --push
else
    git push -u origin main
fi

echo "== 4/4  Publicando a versão v$VERSION =="
gh release create "v$VERSION" --title "Vinyl Player $VERSION" --notes "Versão $VERSION" || echo "(essa versão já existe)"

USER_NAME="$(gh api user --jq .login)"
echo
echo "PRONTO! Em ~10 minutos os instaladores aparecem em:"
echo "  https://github.com/$USER_NAME/vinyl-player/releases"
echo "Acompanhe o andamento em: https://github.com/$USER_NAME/vinyl-player/actions"
