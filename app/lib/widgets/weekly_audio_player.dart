import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';

import '../providers/api_provider.dart';

/// Play button + inline player for the spoken weekly digest (Audio-Digest, P13).
///
/// Audio is fetched lazily on first tap (the backend synthesizes once and
/// caches), written to a temp file and played via just_audio. Degrades to an
/// error row with retry when the backend can't produce audio (e.g. 503).
class WeeklyAudioPlayer extends ConsumerStatefulWidget {
  const WeeklyAudioPlayer({super.key, required this.summaryId});

  final int summaryId;

  @override
  ConsumerState<WeeklyAudioPlayer> createState() => _WeeklyAudioPlayerState();
}

class _WeeklyAudioPlayerState extends ConsumerState<WeeklyAudioPlayer> {
  final AudioPlayer _player = AudioPlayer();
  bool _loading = false;
  bool _loaded = false;
  String? _error;

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _loadAndPlay() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ref.read(apiClientProvider);
      final path = await api.downloadWeeklyAudio(widget.summaryId);
      await _player.setFilePath(path);
      // Reset to start and pause when playback finishes.
      _player.processingStateStream.listen((s) {
        if (s == ProcessingState.completed && mounted) {
          _player.pause();
          _player.seek(Duration.zero);
        }
      });
      if (!mounted) return;
      setState(() {
        _loaded = true;
        _loading = false;
      });
      await _player.play();
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg = code == 503
          ? 'Audio ist auf dem Server nicht verfügbar.'
          : code == 400
              ? 'Diese Woche hat keinen Text zum Vorlesen.'
              : 'Audio konnte nicht geladen werden.';
      if (mounted) {
        setState(() {
          _error = msg;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Audio konnte nicht geladen werden.';
          _loading = false;
        });
      }
    }
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: scheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            _buildButton(scheme),
            const SizedBox(width: 12),
            Expanded(child: _buildBody(scheme)),
          ],
        ),
      ),
    );
  }

  Widget _buildButton(ColorScheme scheme) {
    if (_loading) {
      return const SizedBox(
        width: 48,
        height: 48,
        child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (!_loaded) {
      return IconButton.filled(
        icon: const Icon(Icons.play_arrow),
        iconSize: 28,
        tooltip: 'Wochenrückblick anhören',
        onPressed: _loadAndPlay,
      );
    }
    return StreamBuilder<PlayerState>(
      stream: _player.playerStateStream,
      builder: (context, snapshot) {
        final playing = snapshot.data?.playing ?? false;
        return IconButton.filled(
          icon: Icon(playing ? Icons.pause : Icons.play_arrow),
          iconSize: 28,
          tooltip: playing ? 'Pause' : 'Abspielen',
          onPressed: () => playing ? _player.pause() : _player.play(),
        );
      },
    );
  }

  Widget _buildBody(ColorScheme scheme) {
    if (_error != null) {
      return Row(
        children: [
          Expanded(
            child: Text(
              _error!,
              style: TextStyle(color: scheme.onSecondaryContainer),
            ),
          ),
          TextButton(onPressed: _loadAndPlay, child: const Text('Erneut')),
        ],
      );
    }

    if (!_loaded) {
      return Text(
        'Wochenrückblick anhören',
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: scheme.onSecondaryContainer,
              fontWeight: FontWeight.w600,
            ),
      );
    }

    return StreamBuilder<Duration?>(
      stream: _player.durationStream,
      builder: (context, durSnap) {
        final duration = durSnap.data ?? Duration.zero;
        return StreamBuilder<Duration>(
          stream: _player.positionStream,
          builder: (context, posSnap) {
            var position = posSnap.data ?? Duration.zero;
            if (position > duration) position = duration;
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    trackHeight: 2,
                    thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                    overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
                  ),
                  child: Slider(
                    value: position.inMilliseconds.toDouble().clamp(
                          0,
                          duration.inMilliseconds.toDouble(),
                        ),
                    max: duration.inMilliseconds.toDouble() <= 0
                        ? 1
                        : duration.inMilliseconds.toDouble(),
                    onChanged: (v) =>
                        _player.seek(Duration(milliseconds: v.round())),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Text(
                    '${_fmt(position)} / ${_fmt(duration)}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSecondaryContainer,
                        ),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }
}
