# Wraptile CLI Reference

```
 Usage: wraptile [OPTIONS] COMMAND [ARGS]...                                  
                                                                              
 `wraptile` is a web server made for wrapping workflow  orchestration systems 
 providing an API compliant with the OGC API - Processes, Part 1: Core        
 Standard (https://ogcapi.ogc.org/processes/).                                
                                                                              
 The SERVICE argument may be followed by a `--` to pass one or more           
 service-specific arguments and options.                                      
                                                                              
 Note that the service arguments may also be given by the                     
 environment variable `EOZILLA_SERVICE`.                                      
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --version                     Show version and exit.                       │
│ --install-completion          Install completion for the current shell.    │
│ --show-completion             Show completion for the current shell, to    │
│                               copy it or customize the installation.       │
│ --help                        Show this message and exit.                  │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ run   Run server in production mode.                                       │
│ dev   Run server in development mode.                                      │
╰────────────────────────────────────────────────────────────────────────────╯
```
