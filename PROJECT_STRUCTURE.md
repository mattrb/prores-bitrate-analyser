# ProRes Bitrate Analyser - Project Structure
```
ProRes Analyser/
├── prores_analyser.py          # Main application
├── release.sh                  # Automated build & release script
├── requirements.txt            # Python dependencies
├── README.md                   # User documentation
├── project-roadmap.md          # Development roadmap
├── .gitignore                  # Git ignore rules
├── venv/                       # Virtual environment (not in git)
├── backups/                    # Old versions (not in git)
└── dist/                       # Built app (not in git)
```

## Quick Commands

**Development:**
```bash
source venv/bin/activate
python prores_analyser.py
```

**Release:**
```bash
./release.sh 1.3.0 "Release notes"
```
