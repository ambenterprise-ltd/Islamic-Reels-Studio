[Setup]
AppName=Islamic Reels Studio - Agency Edition
AppVersion=2.0.0
AppPublisher=AMB ENTERPRISE
DefaultDirName={localappdata}\Islamic Reels Studio
DefaultGroupName=Islamic Reels Studio
OutputBaseFilename=IslamicReelsStudio_Setup_v2.0
Compression=lzma2
SolidCompression=yes

PrivilegesRequired=admin
OutputDir=.\InstallerOutput

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; --- 1. The Main Executable & Internal Engine ---
Source: "dist\Islamic Reels Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; --- 2. THE BYPASS: Forcing custom scripts into the app folder ---
Source: "audio_generator.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "video_composer.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "news_gatherer.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "social_engine.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "cloud_logger.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "hardware_optimizer.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "environment_precheck.py"; DestDir: "{app}"; Flags: ignoreversion

; --- 3. Required Asset Folders (Shorts Only) ---
Source: "backgrounds\*"; DestDir: "{app}\backgrounds"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "font\*"; DestDir: "{app}\font"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Assest\*"; DestDir: "{app}\Assest"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "resoursce\*"; DestDir: "{app}\resoursce"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; --- 4. The Automation Media Folders ---
Source: "reciter_clips\*"; DestDir: "{app}\reciter_clips"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "reciter_photos\*"; DestDir: "{app}\reciter_photos"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "sound_effects\*"; DestDir: "{app}\sound_effects"; Flags: ignoreversion recursesubdirs createallsubdirs

; --- 5. Branding & Security Vault ---
Source: "logo.JPG"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "credentials\*"; DestDir: "{app}\credentials"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; --- 6. Configuration Files ---
Source: "settings.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "client_secret.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "sheets_secret.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "token.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Islamic Reels Studio"; Filename: "{app}\Islamic Reels Studio.exe"
Name: "{commondesktop}\Islamic Reels Studio"; Filename: "{app}\Islamic Reels Studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Islamic Reels Studio.exe"; Description: "{cm:LaunchProgram,Islamic Reels Studio}"; Flags: nowait postinstall skipifsilent