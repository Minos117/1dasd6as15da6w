using System;
using System.Diagnostics;
using System.IO;
class L {
  static void Main(string[] a) {
    string d = AppDomain.CurrentDomain.BaseDirectory;
    var p = new ProcessStartInfo(Path.Combine(d, "python\\pythonw.exe"),
      "\"" + Path.Combine(d, "ZaiaRemote.py") + "\" " + string.Join(" ", a));
    p.WorkingDirectory = d; p.UseShellExecute = false;
    Process.Start(p);
  }
}
