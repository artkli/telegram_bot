# telegram bot

uruchomienie jako serwis:

```sh
sudo vi /lib/systemd/system/telegram-bot.service
```

```
  [Unit]
  Description=Telegram Bot Service
  After=multi-user.target
  [Service]
  Type=idle
  ExecStart=/usr/bin/python3 /home/pi/tele/telegram_bot.py
  [Install]
  WantedBy=multi-user.target
```

```sh
sudo chmod 644 /lib/systemd/system/telegram-bot.service
sudo systemctl enable telegram-bot.service
sudo systemctl start telegram-bot.service
```

