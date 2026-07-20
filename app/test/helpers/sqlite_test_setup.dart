import 'dart:ffi';
import 'dart:io';

import 'package:sqlite3/open.dart';

bool _configured = false;

/// Point the `sqlite3` package at the versioned system library.
///
/// CI/dev hosts often ship `libsqlite3.so.0` without the unversioned
/// `libsqlite3.so` symlink (that comes with the `-dev` package), which makes
/// drift's `NativeDatabase.memory()` fail to load its native library. Calling
/// this once before opening an in-memory database fixes that without touching
/// the system. No-op on non-Linux and after the first call.
void useSystemSqlite() {
  if (_configured) return;
  _configured = true;
  if (Platform.isLinux) {
    open.overrideFor(
      OperatingSystem.linux,
      () => DynamicLibrary.open('libsqlite3.so.0'),
    );
  }
}
