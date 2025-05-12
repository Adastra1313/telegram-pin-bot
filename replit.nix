{ pkgs }: {
  deps = [
    pkgs.python39Full
    pkgs.python39Packages.aiogram
    pkgs.python39Packages.python-dotenv
    pkgs.python39Packages.flask
  ];
}
