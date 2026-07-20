import 'package:flutter/material.dart';

/// A list of placeholder cards shown while the first page of items loads.
///
/// Dependency-free: a single [AnimationController] drives a subtle opacity
/// pulse shared by all skeleton blocks, so it reads as "loading" without the
/// bare centered spinner.
class SkeletonList extends StatefulWidget {
  const SkeletonList({super.key, this.itemCount = 6});

  final int itemCount;

  @override
  State<SkeletonList> createState() => _SkeletonListState();
}

class _SkeletonListState extends State<SkeletonList>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 0.4, end: 0.9).animate(_controller),
      child: ListView.builder(
        // Skeletons are non-interactive; don't intercept a pull-to-refresh.
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 80),
        itemCount: widget.itemCount,
        itemBuilder: (context, _) => const _SkeletonCard(),
      ),
    );
  }
}

class _SkeletonCard extends StatelessWidget {
  const _SkeletonCard();

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).colorScheme.onSurface.withAlpha(28);

    Widget block(double width, double height) => Container(
          width: width,
          height: height,
          decoration: BoxDecoration(
            color: base,
            borderRadius: BorderRadius.circular(6),
          ),
        );

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                block(36, 36),
                const SizedBox(width: 12),
                Expanded(child: block(double.infinity, 16)),
              ],
            ),
            const SizedBox(height: 12),
            block(160, 12),
            const SizedBox(height: 12),
            Row(
              children: [
                block(60, 22),
                const SizedBox(width: 8),
                block(80, 22),
                const SizedBox(width: 8),
                block(50, 22),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
