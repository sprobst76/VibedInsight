import 'package:flutter/material.dart';

class NoteData {
  final String title;
  final String text;

  NoteData({required this.title, required this.text});
}

class AddNoteDialog extends StatefulWidget {
  const AddNoteDialog({super.key});

  @override
  State<AddNoteDialog> createState() => _AddNoteDialogState();
}

class _AddNoteDialogState extends State<AddNoteDialog> {
  final _titleController = TextEditingController();
  final _textController = TextEditingController();
  bool _isValid = false;

  @override
  void dispose() {
    _titleController.dispose();
    _textController.dispose();
    super.dispose();
  }

  void _validate() {
    setState(() {
      _isValid = _titleController.text.trim().isNotEmpty &&
          _textController.text.trim().isNotEmpty;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Note'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _titleController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Title',
                hintText: 'Note title',
                prefixIcon: Icon(Icons.title),
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => _validate(),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _textController,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: 'Content',
                hintText: 'Write your note...',
                prefixIcon: Icon(Icons.notes),
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              onChanged: (_) => _validate(),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isValid ? _submit : null,
          child: const Text('Add'),
        ),
      ],
    );
  }

  void _submit() {
    Navigator.of(context).pop(
      NoteData(
        title: _titleController.text.trim(),
        text: _textController.text.trim(),
      ),
    );
  }
}
