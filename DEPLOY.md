# Dejar el bot activo 24/7

El bot (`python main.py`) revisa el mercado cada 15 minutos y omite los ciclos con el
mercado cerrado, así que basta con mantenerlo vivo de forma permanente en una máquina
que no se apague. Estas son las dos formas recomendadas.

## Opción A: systemd (VPS Linux)

```bash
sudo mkdir -p /opt/trading-bot
sudo chown "$USER" /opt/trading-bot
git clone https://github.com/MirandaSource/Trading.git /opt/trading-bot
cd /opt/trading-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# editar .env y rellenar ALPACA_API_KEY y ALPACA_SECRET_KEY
chmod 600 .env

sudo cp deploy/trading-bot.service /etc/systemd/system/trading-bot.service
sudo sed -i "s/User=%i/User=$USER/" /etc/systemd/system/trading-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot
```

Comprobaciones:

```bash
systemctl status trading-bot
tail -f /opt/trading-bot/trading_bot.log
```

`Restart=always` reinicia el bot si el proceso muere, y `enable` lo vuelve a arrancar
tras reiniciar el servidor.

## Opción B: Docker

```bash
git clone https://github.com/MirandaSource/Trading.git trading-bot
cd trading-bot
cp .env.example .env   # rellenar las claves
docker compose up -d --build
docker compose logs -f
```

`restart: unless-stopped` mantiene el contenedor vivo tras fallos y reinicios del host.

## Verificación previa

Antes de dejarlo permanente, ejecuta el pre-vuelo (no envía órdenes):

```bash
python main.py --dry-run
```

## Notas

- El bot fuerza paper trading: aborta si `ALPACA_PAPER=false`.
- No subas nunca el archivo `.env` al repositorio.
- Una sesión de Devin no es infraestructura permanente: el proceso solo vive mientras
  la máquina de la sesión esté activa.
