# Operations Runbook

This runbook provides operational guidance for deploying and maintaining the NexusAgent orchestrator in production environments.

## 🚀 Deployment

### Production Installation
1. **Dependency Install**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configuration**:
   Set the necessary environment variables (see `docs/CONTRIBUTING.md`) or create a `config/nexusagent.yaml` file.
3. **Service Registration**:
   Copy the `nexusagent.service` file to `/etc/systemd/system/` and enable it:
   ```bash
   sudo cp nexusagent.service /etc/systemd/system/
   sudo systemctl enable nexusagent
   sudo systemctl start nexusagent
   ```

### Verification
After deployment, verify the system status:
```bash
python main.py health
```
Expected Output: `✨ System is Healthy!`

## 📈 Monitoring

### Health Checks
The system provides a `/health` endpoint on the API port (default 8000) to monitor connectivity to NATS and the Database.

### Log Management
Logs are streamed to `server.log` in the project root. 
- **Critical**: Look for `CRITICAL` or `ERROR` tags in `server.log`.
- **Trace**: Set `NEXUS_LOG_LEVEL=DEBUG` to trace agent tool executions.

## 🛠️ Troubleshooting

### Issue: `ServiceUnavailableError` (NATS)
**Symptoms**: Server fails to start or `main.py health` reports NATS disconnected.
**Solution**:
1. Verify NATS server is running: `nats-server -js` (JetStream must be enabled).
2. Check if the port `4222` is open.
3. Validate `NEXUS_SERVER__NATS_URL` is correct.

### Issue: Database Locked / Busy
**Symptoms**: `sqlite3.OperationalError: database is locked`.
**Solution**:
1. Ensure only one `NexusWorker` process is writing to the database.
2. Check for orphaned worker processes: `ps aux | grep nexusagent`.

### Issue: Authentication Failure
**Symptoms**: Client cannot submit tasks; "Secure secret missing".
**Solution**:
1. Run the server for the first time to trigger the **Secret Wizard**.
2. Ensure `.master.secret` is persisted and readable by the service user.

## 🔄 Rollback Procedures

### Application Rollback
Revert to the previous stable git commit and restart the systemd service:
```bash
git checkout <stable-commit-hash>
sudo systemctl restart nexusagent
```

### Database Recovery
The state is stored in `nexus.db`. To restore from a backup:
1. Stop the service: `sudo systemctl stop nexusagent`
2. Replace `nexus.db` with the backup copy.
3. Restart the service: `sudo systemctl start nexusagent`
