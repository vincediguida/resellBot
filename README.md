# resellBot

Utility dedicate ad automatizzare attività per reseller. Oltre agli script
presenti in origine è ora disponibile un bot Discord che inoltra in tempo reale
i messaggi di uno o più canali verso un webhook configurabile.

## Discord channel listener

### Requisiti

* Python 3.10+
* Dipendenze: `pip install discord.py aiohttp`

### Configurazione

1. **Crea il bot su Discord**
   1. Apri <https://discord.com/developers/applications> e premi
      **New Application**.
   2. Assegna un nome alla tua applicazione e conferma.
   3. Nella sezione **Bot** scegli **Add Bot** e copia il **token**: servirà
      come `bot_token` nel file di configurazione o nella variabile
      d'ambiente `DISCORD_BOT_TOKEN`.
   4. Abilita le **Privileged Gateway Intents**: attiva *Message Content*,
      *Server Members* non è necessario. Senza l'intent *Message Content* il
      bot non può leggere il testo dei messaggi e quindi non può inoltrarli al
      webhook: per questo specifico listener è quindi obbligatorio abilitarlo.
      Se il bot non è verificato puoi attivarle immediatamente; per i bot
      verificati potrebbe essere richiesta l'approvazione di Discord prima che
      l'impostazione venga applicata.
      > **Nota**: Discord richiede che la tua applicazione abbia un link ai
      > *Termini di servizio* e alla *Privacy policy* prima di consentire
      > l'attivazione delle intent privilegiate. Puoi aggiungerli da
      > **General Information > App Terms of Service URL / App Privacy Policy
      > URL**. Se non disponi già di questi documenti:
      > * personalizza i modelli presenti in `docs/terms_of_service.html` e
      >   `docs/privacy_policy.html` con i dati della tua attività (ragione
      >   sociale, contatti ufficiali, eventuali riferimenti legali);
      > * pubblica le pagine in modo accessibile: puoi caricare i file HTML su un
      >   hosting statico (es. GitHub Pages, Netlify) oppure incollarne il testo
      >   in un documento Google impostato con visibilità "Chiunque abbia il
      >   link";
      > * copia gli URL pubblici nei campi richiesti e salva le modifiche, quindi
      >   torna alla scheda **Bot** per attivare l'intent *Message Content*.
   5. Nella sezione **OAuth2 > URL Generator** seleziona gli scope `bot` e
      `applications.commands`, quindi le permission `Read Messages/View
      Channels` e `Read Message History`. Usa l'URL generato per invitare il
      bot nel server desiderato.

2. **Recupera gli ID dei canali da monitorare**
   * Attiva la modalità sviluppatore su Discord (Impostazioni utente > Avanzate).
   * Clic destro sul canale da tracciare e scegli **Copia ID**.

3. **Configura il webhook di destinazione**
   * Per inoltrare i messaggi in un altro canale Discord: Impostazioni del
     server > Integrazioni > Webhook > Nuovo Webhook, quindi copia l'URL.
   * Per servizi esterni (es. automazioni personalizzate) usa l'endpoint HTTP
     fornito dal servizio.

4. **Prepara il file di configurazione**
   1. Duplica `discord_listener_config.example.json` in
      `discord_listener_config.json`.
   2. Compila i campi principali:
      * `bot_token`: inserisci il token copiato al punto 1 (puoi ometterlo se
        esporti `DISCORD_BOT_TOKEN`).
      * `channels`: elenco degli ID numerici dei canali.
      * `webhook_url`: URL del webhook creato al punto 3.
      * `keywords`: (opzionale) filtri testuali; lascia `[]` per inoltrare tutto.
      * `ignore_bot_messages`: `true` per ignorare i bot, `false` per inoltrare
        anche i bot.
      * `include_attachments`: `true` per includere gli allegati.

5. **(Opzionale) usa la variabile d'ambiente per il token**

   ```bash
   export DISCORD_BOT_TOKEN="INSERISCI_IL_TOKEN"
   ```

### Esecuzione

Avvia il listener con:

```bash
python discord_channel_listener.py --config discord_listener_config.json
```

Opzioni utili:

* `--log-level DEBUG` per visualizzare informazioni dettagliate.
* `--channel 123456789 --channel 987654321` per sovrascrivere la lista dei
  canali direttamente da linea di comando.
* `--keyword restock --keyword shock` per impostare filtri rapidi senza
  modificare il file di config.

Il bot ascolterà i canali indicati e, ad ogni nuovo messaggio compatibile con i
filtri, invierà un payload al webhook configurato. In caso di errori lato
webhook verrà stampato il codice HTTP e il corpo della risposta per aiutare la
diagnosi.
