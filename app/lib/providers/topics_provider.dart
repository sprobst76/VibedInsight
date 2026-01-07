import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/content_item.dart';
import 'api_provider.dart';

final topicsProvider = FutureProvider<List<Topic>>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  return apiClient.getTopics();
});
