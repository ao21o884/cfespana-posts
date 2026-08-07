name: C.F. España Instagram post

on:
  schedule:
    - cron: '0 7 * * 1'
    - cron: '0 19 * * 0'
  workflow_dispatch:
    inputs:
      mode:
        description: 'preview o results'
        default: preview
        required: true

jobs:
  post:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Instalar dependencias
        run: pip install pillow requests beautifulsoup4

      - name: Descarregar CSV actualitzat
        run: |
          curl -L -o Verein-v1368.csv \
            "https://matchcenter.fvbj-afbj.ch/default.aspx?v=1368&oid=6&lng=1&a=vs&format=csv" \
            -H "User-Agent: Mozilla/5.0" || echo "CSV web failed, using local file"

      - name: Decidir modo
        id: mode
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "mode=${{ inputs.mode }}" >> $GITHUB_OUTPUT
          elif [ "${{ github.event.schedule }}" = "0 19 * * 0" ]; then
            echo "mode=results" >> $GITHUB_OUTPUT
          else
            echo "mode=preview" >> $GITHUB_OUTPUT
          fi

      - name: Generar imagen y texto
        run: python cfespana_post.py ${{ steps.mode.outputs.mode }}

      - name: Guardar en repositorio
        run: |
          git config user.name  "cfespana-bot"
          git config user.email "bot@users.noreply.github.com"
          git add out/ cache/ Verein-v1368.csv || true
          git commit -m "post: ${{ steps.mode.outputs.mode }} $(date +%F)" || true
          git push

      - name: Enviar por email
        env:
          EMAIL_FROM:     ${{ secrets.EMAIL_FROM }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_TO:       ${{ secrets.EMAIL_TO }}
        run: |
          for f in out/*.png; do python publish.py "$f"; done
