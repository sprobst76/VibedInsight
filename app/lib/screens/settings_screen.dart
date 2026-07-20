import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_settings.dart';
import '../providers/api_provider.dart';

/// Server-Verbindung konfigurieren: URL + API-Key.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _urlController;
  late final TextEditingController _apiKeyController;
  bool _obscureKey = true;
  bool _saving = false;
  String? _testResult;

  @override
  void initState() {
    super.initState();
    final settings = ref.read(appSettingsProvider);
    _urlController = TextEditingController(text: settings.serverUrl);
    _apiKeyController = TextEditingController(text: settings.apiKey);
  }

  @override
  void dispose() {
    _urlController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _testResult = null;
    });

    final settings = await AppSettings.save(
      serverUrl: _urlController.text,
      apiKey: _apiKeyController.text,
    );
    ref.read(appSettingsProvider.notifier).state = settings;

    // Verbindung testen: erst Erreichbarkeit (/health ist public), dann den
    // API-Key gegen einen geschützten Endpunkt — sonst meldet ein falscher
    // Key trotzdem "erfolgreich".
    final api = ref.read(apiClientProvider);
    final healthy = await api.healthCheck();
    bool? authOk;
    if (healthy) {
      try {
        authOk = await api.checkAuth();
      } catch (_) {
        authOk = null; // erreichbar, aber Key-Check nicht eindeutig
      }
    }

    if (!mounted) return;
    final String result;
    if (!healthy) {
      result = 'Server nicht erreichbar — URL prüfen';
    } else if (authOk == false) {
      result = 'Server erreichbar, aber API-Key ungültig';
    } else if (authOk == null) {
      result = 'Server erreichbar — API-Key nicht prüfbar';
    } else {
      result = 'Verbindung erfolgreich';
    }

    setState(() {
      _saving = false;
      _testResult = result;
    });

    if (healthy && authOk == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Einstellungen gespeichert')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Einstellungen')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Server',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _urlController,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Server-URL',
              hintText: 'https://insight.example.com',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _apiKeyController,
            obscureText: _obscureKey,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: 'API-Key',
              helperText: 'Aus der .env des Servers (API_KEY)',
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                icon: Icon(_obscureKey ? Icons.visibility : Icons.visibility_off),
                onPressed: () => setState(() => _obscureKey = !_obscureKey),
              ),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save),
            label: const Text('Speichern & Verbindung testen'),
          ),
          if (_testResult != null) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(
                  _testResult!.startsWith('Verbindung erfolgreich')
                      ? Icons.check_circle
                      : Icons.error,
                  color: _testResult!.startsWith('Verbindung erfolgreich')
                      ? Colors.green
                      : Theme.of(context).colorScheme.error,
                ),
                const SizedBox(width: 8),
                Expanded(child: Text(_testResult!)),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
