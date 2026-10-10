from html import escape

METHOD_SLUG = "como-lo-calculamos"
ABOUT_SLUG = "sobre-esta-iniciativa"
PRESS_SLUG = "prensa"

NOT_OFFICIAL = (
    '<p class="notice"><strong>Este sitio no es un sistema oficial de alertas.</strong> '
    "Los niveles de «Nuestro análisis» los calculamos nosotros con datos públicos. No son una alerta oficial. "
    "Que no aparezca un nivel alto no significa que no haya peligro. "
    "En una emergencia, siga las indicaciones de SENAPRED y de la autoridad.</p>"
)

METHOD_TITLE = "Cómo lo calculamos"
METHOD_LEAD = "De dónde sale cada dato y cómo decidimos cada nivel"
METHOD_DESCRIPTION = "Qué fuentes cruzamos para cada amenaza en las comunas del Maule, cómo decidimos el nivel y en qué orden mostramos las filas."

METHOD_HTML = (
    NOT_OFFICIAL
    + """
<section class="card" aria-labelledby="indice"><h2 id="indice">En esta página</h2>
<ul class="dots">
<li><a href="#lectura">Cómo leer la página de su comuna</a></li>
<li><a href="#orden">En qué orden van las filas</a></li>
<li><a href="#lluvia">Lluvia, crecidas y aluviones</a></li>
<li><a href="#tiempo">Tiempo</a></li>
<li><a href="#incendios">Incendios</a></li>
<li><a href="#sismos">Sismos</a></li>
<li><a href="#mar">Tsunami y mar</a></li>
<li><a href="#aire">Calidad del aire</a></li>
<li><a href="#fallas">Si una fuente deja de responder</a></li>
<li><a href="#falta">Lo que todavía no tenemos</a></li>
</ul></section>

<section class="card" aria-labelledby="lectura"><h2 id="lectura">Cómo leer la página de su comuna</h2>
<p>Cada amenaza ocupa una fila.</p>
<p>A un lado está el <strong>aviso oficial</strong>. Al otro lado está <strong>nuestro análisis</strong>. En el teléfono, el aviso oficial aparece primero.</p>
<p>Los avisos oficiales son de SENAPRED y de la Dirección Meteorológica de Chile. Los leemos de sus canales públicos, tal como los vería cualquier persona.</p>
<p>Nuestro análisis junta varias fuentes, de Chile y de otros países, y las compara entre sí. Cada análisis tiene un botón para ver las fuentes y los datos que usamos.</p>
<p>Cada nivel se muestra con una palabra y un color: Bajo, Moderado, Alto o Crítico. «Informativo» quiere decir que hay un dato útil, pero no un peligro medido. «Sin datos» quiere decir que la fuente no nos entregó datos recientes.</p>
<p>El sitio se vuelve a armar más o menos cada 15 minutos. En cada vuelta leemos de nuevo todas las fuentes. Arriba de cada página está la hora de la última actualización.</p>
</section>

<section class="card" aria-labelledby="orden"><h2 id="orden">En qué orden van las filas</h2>
<ol class="steps">
<li><strong>Primero, las filas con una alerta oficial vigente.</strong> Después, las filas con una alerta oficial que todavía no empieza.</li>
<li><strong>Después, según nuestro nivel</strong>, del más alto al más bajo.</li>
<li><strong>Si dos filas quedan empatadas, decide la temporada.</strong> Una vez al mes revisamos cómo estuvo el tiempo en los últimos 30 días.</li>
<li><strong>Al final van «Otras alertas oficiales»</strong>: por ejemplo volcanes, o alertas que no calzan en ninguna fila.</li>
</ol>
<h3>Cómo decidimos la temporada</h3>
<p>Medimos dos cosas en Talca, Curicó, Linares y Cauquenes, y sacamos el promedio.</p>
<ul class="dots">
<li><strong>Si llovió más o menos de lo normal.</strong> Usamos el índice de precipitación estandarizado (SPI). Compara la lluvia de los últimos 30 días con la de los mismos días entre 1991 y 2020. Es el índice que recomienda la Organización Meteorológica Mundial.</li>
<li><strong>Si el clima ayudó a los incendios.</strong> Usamos el índice meteorológico de incendios de Canadá (FWI). Se calcula con la temperatura, la humedad, el viento y la lluvia de cada día.</li>
</ul>
<p>Los incendios van primero cuando ese índice está sobre lo normal y no llovió más de lo normal. En cualquier otro caso, va primero la lluvia.</p>
<p>Los datos del tiempo vienen de ERA5, a través de Open-Meteo. También mostramos el índice de El Niño de la NOAA de Estados Unidos, pero solo como contexto: no cambia el orden.</p>
<h3>Filas que no siempre aparecen</h3>
<ul class="dots">
<li>«Tsunami y mar» aparece solo en las comunas con costa, es decir, las que tienen áreas de evacuación por tsunami publicadas por SENAPRED. En otra comuna aparece solo si hay una alerta oficial.</li>
<li>«Calidad del aire» aparece de abril a septiembre. En los otros meses aparece solo si el nivel es Moderado o más alto.</li>
</ul>
</section>

<section class="card" aria-labelledby="lluvia"><h2 id="lluvia">Lluvia, crecidas y aluviones</h2>
<h3>Aviso oficial</h3>
<p>Alertas de SENAPRED por lluvia, crecidas, desbordes, inundaciones o aluviones, y avisos de lluvia de la Dirección Meteorológica de Chile.</p>
<h3>Nuestro análisis: el río principal de la comuna</h3>
<p>Usamos el pronóstico de caudal del modelo GloFAS de Copernicus, un modelo de ríos que cubre todo el mundo. El caudal es la cantidad de agua que lleva el río.</p>
<p>Para cada comuna elegimos el punto del modelo, dentro de la comuna, por donde pasó más agua en el último mes. Ese es el río principal.</p>
<p>El pronóstico mira los próximos 7 días y trae 51 escenarios distintos. Así vemos si la crecida es probable o solo posible.</p>
<p>Comparamos ese pronóstico con tres medidas de crecida: el caudal que se espera una vez cada 2 años, una vez cada 5 años y una vez cada 20 años. Las calculamos como lo hace GloFAS, con las crecidas más grandes de cada año desde 1997.</p>
<p>El clima está cambiando. Por eso revisamos si las crecidas de cada río han ido subiendo o bajando con los años. Si hay un cambio claro, ajustamos esas medidas al año actual.</p>
<h3>Cómo decidimos el nivel</h3>
<ul class="dots">
<li><strong>Alto:</strong> la mitad o más de los 51 escenarios supera el caudal de 5 años.</li>
<li><strong>Moderado:</strong> la mitad o más supera el caudal de 2 años.</li>
<li><strong>Bajo:</strong> en los demás casos.</li>
<li>Nunca marcamos Crítico sin una alerta oficial.</li>
</ul>
<p>Es un modelo, no una medición. No reemplaza las mediciones de la Dirección General de Aguas ni los avisos de SENAPRED. No encontramos un servicio público con esas mediciones en tiempo real.</p>
<p>Para los aluviones todavía no tenemos una fuente propia. Las alertas oficiales de aluvión o remoción en masa se muestran en esta fila.</p>
</section>

<section class="card" aria-labelledby="tiempo"><h2 id="tiempo">Tiempo</h2>
<h3>Aviso oficial</h3>
<p>Avisos, alertas y alarmas de la Dirección Meteorológica de Chile, y alertas de SENAPRED por viento, tormentas, nieve, heladas o calor.</p>
<h3>Nuestro análisis</h3>
<p><strong>Condiciones meteorológicas.</strong> Seguimos los boletines de la Dirección Meteorológica de Chile que cubren la comuna. Un Aviso queda como Moderado, una Alerta como Alto y una Alarma como Crítico. Si un boletín empieza más adelante, el nivel es Informativo. Si no hay ninguno vigente, es Bajo.</p>
<p><strong>Pronóstico del tiempo.</strong> Mostramos la lluvia, las ráfagas de viento y la temperatura máxima pronosticadas para las próximas 48 horas en el centro de la comuna. El pronóstico viene de Open-Meteo.</p>
<p>Además comparamos tres modelos del tiempo: uno de Europa, uno de Estados Unidos y uno de Alemania. La fila dice cuántos de los tres pronostican 30 milímetros de lluvia o más en 24 horas.</p>
<h3>Cómo decidimos el nivel del pronóstico</h3>
<ul class="dots">
<li><strong>Alto:</strong> 60 milímetros de lluvia o más en 24 horas.</li>
<li><strong>Moderado:</strong> 30 milímetros o más en 24 horas.</li>
<li><strong>Bajo:</strong> menos lluvia que eso.</li>
</ul>
<p>Estos límites son nuestros y son provisionales. No son oficiales. El viento y la temperatura se muestran, pero no cambian el nivel.</p>
</section>

<section class="card" aria-labelledby="incendios"><h2 id="incendios">Incendios</h2>
<h3>Aviso oficial</h3>
<p>Alertas de SENAPRED por incendio forestal.</p>
<h3>Nuestro análisis: focos de calor vistos por satélite</h3>
<p>Revisamos los focos de calor detectados dentro de la comuna en las últimas 24 horas. Cruzamos dos sistemas que funcionan por separado: el INPE de Brasil y NASA FIRMS de Estados Unidos.</p>
<p>Los satélites detectan calor, no incendios. Un foco puede ser un incendio forestal, una quema agrícola o una fuente industrial. No está confirmado en terreno.</p>
<h3>Cómo decidimos el nivel</h3>
<ul class="dots">
<li><strong>Alto:</strong> el mismo foco lo ven los dos sistemas, o lo ven dos pasadas de satélite, a menos de 1 kilómetro.</li>
<li><strong>Moderado:</strong> hay al menos un foco, visto una sola vez.</li>
<li><strong>Bajo:</strong> no hay focos.</li>
<li><strong>Sin datos:</strong> ningún sistema se actualizó en las últimas 6 horas.</li>
<li>Nunca marcamos Crítico sin una alerta oficial.</li>
</ul>
<p>Si ve humo o fuego, llame a Bomberos al 132.</p>
<p>Más abajo en la página, en el mapa y en «Peligros permanentes del territorio», está la recurrencia de incendios de SENAPRED con datos de CONAF. Muestra dónde hubo más incendios entre 2020 y 2024. Sirve para prepararse. No es un pronóstico del día.</p>
</section>

<section class="card" aria-labelledby="sismos"><h2 id="sismos">Sismos</h2>
<h3>Aviso oficial</h3>
<p>Alertas de SENAPRED por sismo.</p>
<h3>Nuestro análisis: sismos que ya ocurrieron</h3>
<p>Los sismos no se pueden pronosticar y no lo intentamos.</p>
<p>Mostramos los sismos de magnitud 4,5 o más de las últimas 24 horas, a menos de 200 kilómetros de la comuna.</p>
<p>Cruzamos dos listas de sismos: la del USGS de Estados Unidos y la del EMSC de Europa. La del EMSC incluye los datos del Centro Sismológico Nacional de Chile. Si un sismo aparece en las dos listas, con menos de 90 segundos y 100 kilómetros de diferencia, lo contamos una sola vez.</p>
<h3>Nivel</h3>
<p>Esta fila siempre es Informativo, porque informa de sismos pasados. Si ninguna de las dos listas se actualizó en las últimas 3 horas, dice «Sin datos».</p>
<p>En las comunas con costa recordamos la regla de SENAPRED: si está en el borde costero y el sismo le hace difícil mantenerse en pie, evacúe de inmediato, sin esperar una alerta.</p>
</section>

<section class="card" aria-labelledby="mar"><h2 id="mar">Tsunami y mar</h2>
<p>Esta fila aparece solo en las comunas con costa.</p>
<h3>Aviso oficial</h3>
<p>Alertas de SENAPRED por tsunami o marejadas. Los avisos oficiales de tsunami son los del SHOA y de SENAPRED.</p>
<h3>Nuestro análisis: el nivel del mar ahora</h3>
<p>Usamos los mareógrafos de Constitución y Boyeruca. Un mareógrafo es un instrumento que mide la altura del mar. Estos los opera el SHOA, y la IOC de la UNESCO publica sus datos cada minuto.</p>
<p>Primero quitamos el efecto de la marea. En un día tranquilo, el mar sube y baja menos de 25 centímetros.</p>
<p>También leemos dos boyas DART de la NOAA de Estados Unidos, frente a Valparaíso y frente a Concepción. Miden el océano desde el fondo del mar. Cuando una boya detecta una onda, empieza sola a medir cada minuto. Las boyas publican sus datos con algunas horas de retraso.</p>
<h3>Cómo decidimos el nivel</h3>
<ul class="dots">
<li><strong>Alto:</strong> todos los sensores de un mareógrafo marcan más de 50 centímetros en la última hora. Puede ser un tsunami o una marejada fuerte.</li>
<li><strong>Moderado:</strong> una boya detectó una onda en las últimas 6 horas, pero los mareógrafos de la costa no muestran nada anormal.</li>
<li><strong>Bajo:</strong> el mar se comporta con normalidad.</li>
<li><strong>Sin datos:</strong> ni los mareógrafos ni las boyas enviaron datos recientes.</li>
</ul>
<p>La señal de los mareógrafos llega unos 15 minutos tarde. Si está en el borde costero y un sismo le hace difícil mantenerse en pie, no espere esta señal: evacúe de inmediato hacia un punto de encuentro o zona segura.</p>
<p>Más abajo en la página, el mapa muestra las áreas de evacuación por tsunami y los puntos de encuentro publicados por SENAPRED.</p>
</section>

<section class="card" aria-labelledby="aire"><h2 id="aire">Calidad del aire</h2>
<h3>Aviso oficial</h3>
<p>Los episodios críticos de contaminación los declara la autoridad. Nuestro cálculo no es una declaración de episodio.</p>
<h3>Nuestro análisis: el material particulado fino</h3>
<p>Medimos el material particulado fino, conocido como MP2,5. Son partículas muy pequeñas en el aire, por ejemplo de humo.</p>
<p>Usamos las estaciones del Sistema de Información Nacional de Calidad del Aire (SINCA), del Ministerio del Medio Ambiente, que estén en la comuna o a menos de 5 kilómetros. Sacamos el promedio de las últimas 24 horas. Necesitamos al menos 18 horas con datos.</p>
<h3>Cómo decidimos el nivel</h3>
<p>Usamos los límites de la norma chilena de MP2,5 (Decreto Supremo 12 de 2011), en microgramos por metro cúbico:</p>
<ul class="dots">
<li><strong>Crítico:</strong> 170 o más, nivel de emergencia.</li>
<li><strong>Alto:</strong> 110 o más, nivel de preemergencia.</li>
<li><strong>Moderado:</strong> 80 o más, nivel de alerta.</li>
<li><strong>Bajo:</strong> menos de 80.</li>
</ul>
<p>El SINCA publica estos datos en línea sin validar. Pueden corregirse después.</p>
</section>

<section class="card" aria-labelledby="fallas"><h2 id="fallas">Si una fuente deja de responder</h2>
<p>Cada página dice cuántas fuentes están respondiendo. Para cada fuente de alertas muestra si funciona y la hora del último dato que recibimos.</p>
<p>Si la página de alertas de SENAPRED no responde, lo decimos arriba de la página y seguimos mostrando lo último que recibimos. Nuestro análisis sigue funcionando con las fuentes que sí responden.</p>
</section>

<section class="card" aria-labelledby="falta"><h2 id="falta">Lo que todavía no tenemos</h2>
<ul class="dots">
<li>Análisis propio para volcanes, calor extremo y marejadas.</li>
<li>Una fuente propia para aluviones y remoción en masa.</li>
<li>Las mediciones de las estaciones de la Dirección Meteorológica de Chile.</li>
<li>Las mediciones de caudal en tiempo real de la Dirección General de Aguas.</li>
</ul>
<p>Cuando una fila no tiene análisis propio, lo dice: «Todavía no tenemos análisis propio para esta amenaza».</p>
</section>
"""
)

ABOUT_TITLE = "Sobre esta iniciativa"
ABOUT_LEAD = "Quién hace este sitio y para qué"
ABOUT_DESCRIPTION = "Riesgo en mi comuna, Región del Maule: una iniciativa de la oficina de la senadora Paulina Vodanovic."

ABOUT_HTML = (
    """
<section class="card" aria-labelledby="quien"><h2 id="quien">Quién lo hace</h2>
<p>«Riesgo en mi comuna, Región del Maule» es una iniciativa de la oficina de la senadora Paulina Vodanovic.</p>
</section>

<section class="card" aria-labelledby="para-que"><h2 id="para-que">Para qué sirve</h2>
<p>Cuando la información oficial no está disponible, la gente igual necesita saber.</p>
<p>Por eso el sitio junta en un solo lugar, para cada una de las 30 comunas del Maule:</p>
<ul class="dots">
<li>las alertas oficiales vigentes,</li>
<li>nuestro propio análisis de cada amenaza, con sus fuentes,</li>
<li>un mapa con los peligros de la comuna,</li>
<li>los teléfonos de emergencia y los enlaces a la información oficial.</li>
</ul>
<p>El sitio lee varias fuentes que funcionan por separado, de Chile y de otros países. Si una deja de responder, la página lo dice, guarda lo último que recibió y sigue con las que sí responden.</p>
<p>No pide registro.</p>
</section>

<section class="card" aria-labelledby="por-que"><h2 id="por-que">Por qué existe este sitio</h2>
<p>En el Maule, los canales oficiales ya han fallado. Durante la crecida de junio de 2023, la Contraloría constató que SENAPRED no envió la alerta masiva por inundación en Rauco, Hualañé y Licantén (<a href="https://www.cnnchile.com/pais/contraloria-revela-fallas-senapred-sistema-frontal-maule-no-alerto-amenaza-inundacion_20240312/" rel="noreferrer">CNN Chile, 12 de marzo de 2024</a>).</p>
<p>Hoy SENAPRED tiene menos recursos. Según <a href="https://www.meganoticias.cl/nacional/533626-presupuesto-senapred-recorte-gestion-riesgo-desastres-2027-09-10-2026.html" rel="noreferrer">Mega Investiga (9 de octubre de 2026)</a>, el proyecto de Presupuesto 2027 que el Gobierno del Presidente José Antonio Kast ingresó al Congreso (<a href="https://www.emol.com/noticias/Economia/2026/09/30/1212889/gobierno-ingresa-proyecto-presupuesto-2027.html" rel="noreferrer">Emol, 30 de septiembre de 2026</a>) baja en 30,6% su Programa de Gestión del Riesgo de Desastres. La asociación de funcionarios del servicio dice que no se pueden reemplazar a quienes se van, salvo en alerta temprana (<a href="https://eldesconcierto.cl/actualidad/funcionarios-senapred-levantan-alerta-crisis-laboral-y-humana-pone-riesgo-chile-n5462614" rel="noreferrer">El Desconcierto, 28 de septiembre de 2026</a>).</p>
<p>Por eso este sitio sigue funcionando aunque falle un canal oficial: cruza varias fuentes independientes y muestra cuáles responden.</p>
</section>

<section class="card" aria-labelledby="que-no-es"><h2 id="que-no-es">Lo que no es</h2>
<p>No es un sistema oficial de alertas. No reemplaza a SENAPRED, al SHOA ni a la Dirección Meteorológica de Chile. Usamos sus datos públicos, pero el sitio no habla en nombre de ellos.</p>
<p>En una emergencia, siga las indicaciones de SENAPRED y de la autoridad.</p>
</section>
"""
)

PRESS_TITLE = "Prensa"
PRESS_LEAD = "Descripción del sitio e imágenes para descargar"
PRESS_DESCRIPTION = "Material de prensa de Riesgo en mi comuna, Región del Maule: descripción breve, logo e imágenes para descargar."

PRESS_ASSETS = (
    ("senator-logo.png", "Logo de la senadora Paulina Vodanovic", "Imagen PNG blanca con fondo transparente, para usar sobre un fondo oscuro.", "logo", "292 × 168 píxeles"),
    ("og-maule.jpg", "Imagen para compartir", "La imagen que aparece al compartir el sitio en redes sociales y mensajería.", "photo", "1200 × 630 píxeles, JPG"),
    ("senator-banner.webp", "Franja de la cabecera", "El fondo azul de la cabecera del sitio, con la silueta del Maule.", "photo", "1600 × 200 píxeles, WebP"),
)


def press_html(base_url: str, assets: list[tuple[str, str, str, str, str]]) -> str:
    site = f"{base_url}/"
    summary = (
        f"«Riesgo en mi comuna, Región del Maule» ({site}) es una iniciativa de la oficina de la senadora Paulina Vodanovic. "
        "Para cada una de las 30 comunas del Maule muestra en una sola página las alertas oficiales vigentes y un análisis propio por amenaza: "
        "lluvia y crecidas, tiempo, incendios, sismos y, según la comuna y la época del año, tsunami y calidad del aire. "
        "Donde es posible, el análisis cruza fuentes independientes de Chile y de otros países, y siempre muestra las fuentes que usa. "
        "Si una fuente deja de responder, la página lo indica y sigue con las que responden. "
        "Se actualiza más o menos cada 15 minutos y no pide registro. "
        "No es un sistema oficial de alertas: en una emergencia, siga las indicaciones de SENAPRED y de la autoridad."
    )
    items = "".join(
        f'<li class="asset"><div class="thumb thumb-{kind}"><img src="../assets/{escape(name)}" alt="" loading="lazy"></div>'
        f'<div><p><strong>{escape(label)}</strong></p><p class="meta">{escape(detail)} {escape(facts)}</p>'
        f'<p><a href="../assets/{escape(name)}" download>Descargar {escape(name)}</a></p></div></li>'
        for name, label, detail, kind, facts in assets
    )
    return f"""
<section class="card" aria-labelledby="breve"><h2 id="breve">Descripción breve</h2>
<p>{escape(summary)}</p>
<p class="meta">Puede copiar este texto tal como está.</p>
</section>

<section class="card" aria-labelledby="datos"><h2 id="datos">Datos del sitio</h2>
<ul class="facts">
<li><strong>Nombre:</strong> Riesgo en mi comuna, Región del Maule</li>
<li><strong>Dirección:</strong> <a href="{escape(site)}">{escape(site)}</a></li>
<li><strong>Iniciativa de:</strong> la oficina de la senadora Paulina Vodanovic</li>
<li><strong>Cobertura:</strong> las 30 comunas de la Región del Maule</li>
<li><strong>Actualización:</strong> más o menos cada 15 minutos</li>
<li><strong>Cómo se calcula:</strong> <a href="../{METHOD_SLUG}/index.html">Cómo lo calculamos</a></li>
</ul>
</section>

<section class="card" aria-labelledby="contacto"><h2 id="contacto">Contacto de prensa</h2>
<p>Oficina de la senadora Paulina Vodanovic, Senado de Chile.</p>
<p>Correo: <a href="mailto:pvodanovic@senado.cl">pvodanovic@senado.cl</a></p>
<p>Teléfonos del Senado: <a href="tel:+56322504000">(56-32) 250 4000</a> y <a href="tel:+56225196700">(56-2) 2519 6700</a>.</p>
</section>

<section class="card" aria-labelledby="descargas"><h2 id="descargas">Imágenes para descargar</h2>
<ul class="assets">{items}</ul>
</section>
"""
