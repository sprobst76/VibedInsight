import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:graphview/GraphView.dart';

import '../api/api_client.dart';
import '../models/content_item.dart';
import '../providers/api_provider.dart';

/// Provider for graph data
final graphDataProvider = FutureProvider<GraphData>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  return apiClient.getGraphData();
});

/// Topic color mapping for visual clustering
class TopicColors {
  static final Map<String, Color> _cache = {};
  static final List<Color> _palette = [
    Colors.blue,
    Colors.green,
    Colors.orange,
    Colors.purple,
    Colors.teal,
    Colors.pink,
    Colors.indigo,
    Colors.amber,
    Colors.cyan,
    Colors.deepOrange,
  ];
  static int _colorIndex = 0;

  static Color getColor(String? topic) {
    if (topic == null) return Colors.grey;

    // Check for common topic patterns
    final lowerTopic = topic.toLowerCase();
    if (lowerTopic.contains('yoga') || lowerTopic.contains('übung') ||
        lowerTopic.contains('fitness') || lowerTopic.contains('training')) {
      return Colors.green;
    }
    if (lowerTopic.contains('ki') || lowerTopic.contains('ai') ||
        lowerTopic.contains('robot') || lowerTopic.contains('intelligen')) {
      return Colors.blue;
    }
    if (lowerTopic.contains('tech') || lowerTopic.contains('computer') ||
        lowerTopic.contains('usb') || lowerTopic.contains('pc')) {
      return Colors.purple;
    }

    // Fallback to cached or new color
    if (!_cache.containsKey(topic)) {
      _cache[topic] = _palette[_colorIndex % _palette.length];
      _colorIndex++;
    }
    return _cache[topic]!;
  }
}

class GraphScreen extends ConsumerStatefulWidget {
  const GraphScreen({super.key});

  @override
  ConsumerState<GraphScreen> createState() => _GraphScreenState();
}

class _GraphScreenState extends ConsumerState<GraphScreen> {
  final Graph graph = Graph();
  final TransformationController _transformationController = TransformationController();
  GraphNode? _selectedNode;

  late FruchtermanReingoldAlgorithm algorithm;

  @override
  void initState() {
    super.initState();
    final config = FruchtermanReingoldConfiguration(
      iterations: 1000,
      repulsionRate: 0.5,
      attractionRate: 0.2,
    );
    algorithm = FruchtermanReingoldAlgorithm(config);
  }

  @override
  void dispose() {
    _transformationController.dispose();
    super.dispose();
  }

  void _buildGraph(GraphData data) {
    graph.nodes.clear();
    graph.edges.clear();

    // Create node map for edge lookup
    final nodeMap = <String, Node>{};

    for (final node in data.nodes) {
      final graphNode = Node.Id(node.id);
      nodeMap[node.id] = graphNode;
      graph.addNode(graphNode);
    }

    // Add edges
    for (final edge in data.edges) {
      final sourceNode = nodeMap[edge.source];
      final targetNode = nodeMap[edge.target];
      if (sourceNode != null && targetNode != null) {
        graph.addEdge(sourceNode, targetNode);
      }
    }
  }

  Widget _buildNodeWidget(Node node, GraphData data) {
    final nodeData = data.nodes.firstWhere(
      (n) => n.id == node.key?.value,
      orElse: () => GraphNode(id: '', title: 'Unknown', topicCount: 0),
    );

    final isSelected = _selectedNode?.id == nodeData.id;
    final color = TopicColors.getColor(nodeData.primaryTopic);

    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedNode = isSelected ? null : nodeData;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? color : color.withOpacity(0.8),
          borderRadius: BorderRadius.circular(12),
          border: isSelected
              ? Border.all(color: Colors.white, width: 3)
              : null,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.2),
              blurRadius: 4,
              offset: const Offset(2, 2),
            ),
          ],
        ),
        constraints: const BoxConstraints(maxWidth: 150),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              nodeData.shortTitle,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            if (nodeData.topicCount > 0) ...[
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '${nodeData.topicCount} topics',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 9,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final graphDataAsync = ref.watch(graphDataProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Knowledge Graph'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(graphDataProvider),
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.center_focus_strong),
            onPressed: () {
              _transformationController.value = Matrix4.identity();
            },
            tooltip: 'Reset View',
          ),
        ],
      ),
      body: graphDataAsync.when(
        loading: () => const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Loading graph...'),
            ],
          ),
        ),
        error: (error, stack) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text('Error: $error'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref.invalidate(graphDataProvider),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (data) {
          if (data.nodes.isEmpty) {
            return const Center(
              child: Text('No items to display'),
            );
          }

          _buildGraph(data);

          return Column(
            children: [
              // Stats bar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _StatChip(
                      icon: Icons.article,
                      label: '${data.nodeCount} Items',
                    ),
                    _StatChip(
                      icon: Icons.link,
                      label: '${data.edgeCount} Relations',
                    ),
                  ],
                ),
              ),

              // Graph view
              Expanded(
                child: InteractiveViewer(
                  constrained: false,
                  transformationController: _transformationController,
                  boundaryMargin: const EdgeInsets.all(200),
                  minScale: 0.1,
                  maxScale: 3.0,
                  child: GraphView(
                    graph: graph,
                    algorithm: algorithm,
                    paint: Paint()
                      ..color = Colors.grey.withOpacity(0.5)
                      ..strokeWidth = 2
                      ..style = PaintingStyle.stroke,
                    builder: (Node node) {
                      return _buildNodeWidget(node, data);
                    },
                  ),
                ),
              ),

              // Selected node info
              if (_selectedNode != null)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 8,
                        offset: const Offset(0, -2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _selectedNode!.title,
                              style: Theme.of(context).textTheme.titleMedium,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close),
                            onPressed: () {
                              setState(() {
                                _selectedNode = null;
                              });
                            },
                          ),
                        ],
                      ),
                      if (_selectedNode!.source != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          _selectedNode!.source!,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.grey,
                              ),
                        ),
                      ],
                      if (_selectedNode!.topics.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: _selectedNode!.topics.map((topic) {
                            return Chip(
                              label: Text(topic),
                              labelStyle: const TextStyle(fontSize: 11),
                              padding: EdgeInsets.zero,
                              visualDensity: VisualDensity.compact,
                              backgroundColor: TopicColors.getColor(topic).withOpacity(0.2),
                            );
                          }).toList(),
                        ),
                      ],
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _StatChip({
    required this.icon,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: Colors.grey),
        const SizedBox(width: 4),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}
