# Squoosher

Batch image compressor CLI — like [Squoosh.app](https://squoosh.app) but in batch mode.

Scans a folder recursively for raster images and compresses them to WebP format, including animated GIF to animated WebP.

---

## Installation

```bash
git clone https://github.com/your-user/squoosher.git
cd squoosher
pip install .
```

For development (editable install):

```bash
pip install -e .
```

**Requirements:** Python 3.10+

---

## Usage

```bash
# Compress all images in a folder (quality 80, default)
squoosher /path/to/project

# Custom quality (1-100)
squoosher /path/to/project --quality 60

# Resize images (downscale only, keeps aspect ratio)
squoosher /path/to/project --max-width 1920 --max-height 1080

# Dry run — list files without converting
squoosher /path/to/project --dry-run

# Skip files that already have a .webp version
squoosher /path/to/project --skip-existing

# Disable recursive scan
squoosher /path/to/project --no-recursive

# Recompress existing .webp files
squoosher /path/to/project --recompress

# Verbose output with per-file breakdown
squoosher /path/to/project --verbose
```

### Supported Formats

| Input | Output |
|-------|--------|
| PNG (with alpha) | WebP |
| JPG / JPEG | WebP |
| GIF (static and animated) | WebP (animated) |
| BMP | WebP |
| TIFF / TIF | WebP |

### Excluded

SVG, EPS, AI, PDF, and any file that can't be opened as a raster image.

### Skipped Folders

`node_modules`, `.git`, `__pycache__`, `dist`, `build`, and hidden files/folders (prefixed with `.`).

---

## Example Output

```
Scanning /home/user/project...

Found 47 eligible images (12.4 MB total)
  PNG: 23  |  JPG: 18  |  GIF: 4  |  BMP: 2

Processing with quality=80, max_width=1920

 [================================] 47/47 — 100%

Done!

+--------------------------------------+
|        Compression Report            |
+--------------------------------------+
| Processed:    45                     |
| Skipped:       2 (already exist)     |
| Failed:        0                     |
|                                      |
| Original size:   12.4 MB            |
| Compressed size:  3.8 MB            |
| Saved:            8.6 MB (69.4%)    |
+--------------------------------------+
```

---

---

# Squoosher (PT-BR)

Compressor de imagens em lote via CLI — como o [Squoosh.app](https://squoosh.app), mas em modo batch.

Escaneia uma pasta recursivamente buscando imagens raster e comprime para o formato WebP, incluindo GIF animado para WebP animado.

---

## Instalacao

```bash
git clone https://github.com/your-user/squoosher.git
cd squoosher
pip install .
```

Para desenvolvimento (instalacao editavel):

```bash
pip install -e .
```

**Requisitos:** Python 3.10+

---

## Uso

```bash
# Comprimir todas as imagens de uma pasta (qualidade 80, padrao)
squoosher /caminho/do/projeto

# Qualidade personalizada (1-100)
squoosher /caminho/do/projeto --quality 60

# Redimensionar imagens (apenas reduz, mantem proporcao)
squoosher /caminho/do/projeto --max-width 1920 --max-height 1080

# Simulacao — lista os arquivos sem converter
squoosher /caminho/do/projeto --dry-run

# Pular arquivos que ja possuem versao .webp
squoosher /caminho/do/projeto --skip-existing

# Desativar busca recursiva
squoosher /caminho/do/projeto --no-recursive

# Recomprimir arquivos .webp existentes
squoosher /caminho/do/projeto --recompress

# Saida detalhada com resultado por arquivo
squoosher /caminho/do/projeto --verbose
```

### Formatos Suportados

| Entrada | Saida |
|---------|-------|
| PNG (com transparencia) | WebP |
| JPG / JPEG | WebP |
| GIF (estatico e animado) | WebP (animado) |
| BMP | WebP |
| TIFF / TIF | WebP |

### Excluidos

SVG, EPS, AI, PDF e qualquer arquivo que nao possa ser aberto como imagem raster.

### Pastas Ignoradas

`node_modules`, `.git`, `__pycache__`, `dist`, `build` e arquivos/pastas ocultos (prefixados com `.`).

---

## Exemplo de Saida

```
Scanning /home/usuario/projeto...

Found 47 eligible images (12.4 MB total)
  PNG: 23  |  JPG: 18  |  GIF: 4  |  BMP: 2

Processing with quality=80, max_width=1920

 [================================] 47/47 — 100%

Done!

+--------------------------------------+
|        Compression Report            |
+--------------------------------------+
| Processed:    45                     |
| Skipped:       2 (already exist)     |
| Failed:        0                     |
|                                      |
| Original size:   12.4 MB            |
| Compressed size:  3.8 MB            |
| Saved:            8.6 MB (69.4%)    |
+--------------------------------------+
```
