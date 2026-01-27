"""
Compactador de Imagens com Preservação de EXIF e GPS

Propósito:
    Comprimir imagens em bytes mantendo metadados EXIF (incluindo GPS) sempre que possível,
    fornecendo informação sobre o formato resultante e coordenadas GPS extraídas.

Responsabilidades principais:
    - Detectar o formato de imagem a partir dos bytes (números mágicos) e validar input.
    - Preservar e re-aplicar metadados EXIF ao salvar a versão comprimida.
    - Converter modos de cor e tratar transparência para garantir compatibilidade com JPEG.
    - Extrair e reportar coordenadas GPS (latitude/longitude) presentes no EXIF.

Posição na arquitetura:
    - Componente utilitário na camada de processamento de mídia/ingestão.
    - Deve ser usado por serviços que recebem imagens brutas antes de armazenar ou servir,
      por exemplo, pipelines de upload, microserviços de processamento de imagens ou
      funções serverless responsáveis por otimizar imagens para armazenamento/entrega.

Dependências críticas:
    - Pillow (PIL): abertura, manipulação, transposição por EXIF, conversões de modo e salvamento.
    - io: buffers em memória (BytesIO) para leitura/escrita de bytes.
    - typing (opcional): para anotações de tipo que melhoram manutenção.

Considerações de segurança:
    - Metadados EXIF podem conter dados sensíveis (especialmente coordenadas GPS) — não os divulgue
      em contextos públicos sem consentimento. Considere remover EXIF quando necessário.
    - Valide o tamanho dos buffers de entrada para evitar consumo excessivo de memória (DoS).
    - Não confie cegamente em formatos inferidos por bytes; trate exceções ao abrir/imprimir imagens.
    - Ao salvar, limite parâmetros (por exemplo, quality) e sanitize entradas provenientes de usuários
      (não usar caminhos/nomes recebidos sem validação).

Exemplo de uso básico:
    from image import compress_bytes
    with open("foto_original.jpg", "rb") as f:
        original = f.read()
    resultado = compress_bytes(85, original)
    if resultado.get("Error"):
        print("Erro:", resultado["Error"])
    else:
        print("Formato:", resultado["format"])
        print("Bytes comprimidos:", len(resultado["data"]))
        print("Contém GPS:", resultado["has_gps"])
        print("Coordenadas GPS:", resultado["gps_coordinates"])
"""

import io
import logging
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
from typing import Union, Optional, Dict, Tuple

logger = logging.getLogger(__name__)

def _detect_image_format(image_bytes: Union[bytes, bytearray]):
    """
    Detecta formato da imagem pelos bytes iniciais (números mágicos)
    
    Parâmetros:
        image_bytes: Bytes da imagem
    
    Retorno:
        str: Formato detectado ('JPEG', 'PNG', 'GIF', 'WebP', 'TIFF', 'BMP', 'Unknown')
    """

    # Converter para bytes se for bytearray
    if isinstance(image_bytes, bytearray):
        image_bytes = bytes(image_bytes)
    
    # Números mágicos para diferentes formatos
    if image_bytes.startswith(b'\xff\xd8\xff'): # type: ignore
        return 'JPEG'
    elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'): # type: ignore
        return 'PNG'
    elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'): # type: ignore
        return 'GIF'
    elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]: # type: ignore
        return 'WebP'
    elif image_bytes.startswith(b'II*\x00') or image_bytes.startswith(b'MM\x00*'): # type: ignore
        return 'TIFF'
    elif image_bytes.startswith(b'BM'): # type: ignore
        return 'BMP'
    else:
        return 'Unknown'

def _convert_to_degrees(value):
    """
    Converte coordenadas GPS do formato DMS para decimal
    
    Parâmetros:
        value: Tupla com (graus, minutos, segundos)
    
    Retorno:
        float: Coordenada em graus decimais
    """
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)

def extract_gps_coordinates(exif_data) -> Optional[Dict[str, float]]:
    """
    Extrai coordenadas GPS do EXIF se disponíveis
    
    Parâmetros:
        exif_data: Dados EXIF da imagem
    
    Retorno:
        Dict com 'latitude' e 'longitude' ou None se não houver GPS
    """
    if not exif_data:
        return None
    
    gps_info = {}
    
    # Procurar pela tag GPS (tag 34853)
    for tag, value in exif_data.items():
        tag_name = TAGS.get(tag, tag)
        if tag_name == "GPSInfo":
            # Processar informações GPS
            for gps_tag in value:
                sub_tag = GPSTAGS.get(gps_tag, gps_tag)
                gps_info[sub_tag] = value[gps_tag]
            break
    
    # Se não houver informações GPS, retornar None
    if not gps_info:
        return None
    
    # Extrair latitude
    if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
        lat = _convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] == 'S':
            lat = -lat
    else:
        return None
    
    # Extrair longitude
    if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
        lon = _convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] == 'W':
            lon = -lon
    else:
        return None
    
    return {
        'latitude': lat,
        'longitude': lon
    }

def has_gps_data(exif_data) -> bool:
    """
    Verifica se o EXIF contém dados GPS
    
    Parâmetros:
        exif_data: Dados EXIF da imagem
    
    Retorno:
        bool: True se contém GPS, False caso contrário
    """
    if not exif_data:
        return False
    
    for tag, value in exif_data.items():
        tag_name = TAGS.get(tag, tag)
        if tag_name == "GPSInfo":
            return True
    
    return False

def compress_bytes(quality: int, image_bytes: Union[bytes, bytearray]):
    """
    Comprime imagem por bytes preservando EXIF/GPS
    
    Parâmetros:
        quality: Qualidade JPEG (1-95, recomendado: 75-90)
        image_bytes: Bytes da imagem original

    Retorno:
        bytearray: Bytes da imagem comprimida
    """
    try:

        # Converter para bytes se for bytearray
        if isinstance(image_bytes, bytearray):
            image_bytes = bytes(image_bytes)

        # Detectar formato (opcional, mas útil para validação)
        format = _detect_image_format(image_bytes)

        # Abrir imagem dos bytes
        input_buffer = io.BytesIO(image_bytes)
        
        with Image.open(input_buffer) as img:

            # Corrigir orientação baseada no EXIF
            img = ImageOps.exif_transpose(img)
            
            # Obter EXIF original (inclui GPS automaticamente)
            exif = img.getexif()
            
            # Converter para RGB se necessário (para JPEG)
            if img.mode in ('RGBA', 'P', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if len(img.split()) == 4:  # Tem canal alpha
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Buffer de saída
            output_buffer = io.BytesIO()
            
            # Salvar comprimido com EXIF preservado
            img.save(
                output_buffer,
                format=format,
                quality=quality,
                optimize=True,
                exif=exif  # Preserva GPS e todos os metadados
            )
            
            # Extrair coordenadas GPS se disponíveis
            gps_coords = extract_gps_coordinates(exif)
            has_gps = has_gps_data(exif)
            
            # Retornar como bytearray
            data_bytes = bytearray(output_buffer.getvalue())
            return {
                "format": format, 
                "data": data_bytes, 
                "Error": None, 
                "exif": exif,
                "has_gps": has_gps,
                "gps_coordinates": gps_coords
            }

    except Exception as e:
        logger.error(f"Erro ao comprimir imagem: {e}")
        return {"format": None, "data": None, "Error": str(e)}