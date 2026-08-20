"""Formatos numéricos para locale 'es'.

TuClima usa español en la UI, pero los datos meteorológicos/científicos
deben mostrarse con punto decimal (12.5) y no con coma (12,5).
"""

DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ''
NUMBER_GROUPING = 0
USE_THOUSAND_SEPARATOR = False
