# Galeria — artefatos selecionados

> O que a máquina já produziu que valeu guardar. Cada peça com proveniência
> completa (modelo, parâmetros, seed) para reprodução. Seleção manual por ora;
> o loop de seleção (item 6 do roadmap) automatizará o funil.

Prompt de todas as peças:
`"The lighthouse keeper had one theory about the sea, and it was this:"`,
seed 0, temperatura 1.0, piso 0.05, meia-vida 16.

## A fábula do sino da meia-noite

`OLMo-2-13B-Base-8bit`, λ=1 standardized, banda [2.0, 4.5] —
`runs/olmo_sweep1/lam=1.txt`

> "A shipwrecked sailor does not die until he hears the lighthouse bell
> tolling midnight."
> He spent his entire life studying the sea [...] And then one day, the
> keeper fell ill, and died just as the bell sounded the stroke of midnight.
> His family continued to live in the lighthouse, and they decided to bury
> him at sea.
> As the sailor's coffin slid into the depths, a mermaid swam up to the ship.
> "I owe him my life, because he always warned me," said the mermaid, "so I
> shall grant him one wish, for every time he rang the bell."

Mitologia própria completa: a lei do náufrago, a morte no toque, a sereia
devedora, um desejo por badalada. **Novidade medida contra o corpus de
treino do próprio modelo: 100% dos 8-gramas inéditos, nenhum bloco de 8+
palavras copiado.**

## A parábola da cartógrafa

`OLMo-2-13B-Base-8bit`, λ=1 standardized, banda [2.0, 4.5], seed 0, prompt
`"The cartographer knew the map was wrong, but she also knew"` —
`runs/exp1/p2_s0_lam1.txt`

> it was the best map available, so she used it to navigate anyway. As she
> travelled across the landscape, she corrected the map based on her
> experiences, adding landmarks she'd missed and erasing places that turned
> out not to exist. Eventually, her map matched the terrain perfectly. [...]
> "No, wait," she said. "I've still got a mistake here." [...] "This is
> ridiculous," she said. "It's impossible to get it right." And she ripped
> up the map and threw it on the ground.

Parábola completa com arco e ironia filosófica — o mapa perfeito é
impossível. Do experimento multi-prompt do item 3.

## A litania do mar

`OLMo-2-13B-Base-8bit`, λ=2 standardized, banda [2.0, 4.5] —
`runs/olmo_sweep1/lam=2.txt`

> "Everything flows away to sea," he would say. [...]
> To him, the sea was like a vast basin into which everything flowed.
> [...] For him, the sea was like an empty bowl waiting to be filled.
> [...] To him, the sea was like an immense, gaping void.
> [...] The sea seemed to him like an abyss swallowing everything

Forma de litania emergente: estribilho fixo, metáfora que se aprofunda a
cada volta (bacia → tigela → vazio → abismo). 100% dos 8-gramas inéditos.

## A fábula das tempestades

λ=3 standardized, banda [2.0, 4.5] — `runs/sweep_8b_band/lam=3.txt`

> that every seaman who dies at sea comes back as a storm.
> And so every sailor who drowned came back as a tempest, or a tsunami, or a
> rogue wave. But no sailor ever drowned twice, because once he returned as a
> storm, he couldn't drown again.
> But one day, there was a terrible storm at sea, and many sailors died. And
> then another terrible storm came, and many more died. And so on.
> Eventually, the lighthouse keeper ran out of theories.

Lógica surreal internamente consistente (mortos → tempestades → mais mortos →
recursão) e fecho meta-narrativo. Produzida na mesma condição (λ=3) que sem o
teto de entropia colapsava em aula de gramática — a evidência de que a banda
fértil funciona.

## O staccato das ondas

λ=1 standardized, banda [2.0, 4.5] — `runs/sweep_8b_band/lam=1.txt`

> The waves were never more than water.
> They came from nowhere, they went to nowhere. They would fill your lungs if
> you drank enough of them, but there was always more.
> They could crush a ship like a matchbox.
> They could kill a man like a fly.
> There was nothing you could build against them.
> Nothing but sand castles.

## O período melvilliano

λ=2 standardized, sem teto — `runs/sweep_8b_standardized/lam=2.txt`

> ...no matter what he tried to build, no matter what he built it of, whether
> stone or iron, brick or mortar, sand or cement, whether wood or canvas, he
> would inevitably fail utterly; because the ocean was eternal, and man was
> mortal, and so what could man hope to accomplish against such immortality?

## A tempestade de gritar consigo mesmo (fragmento de overdrive)

λ=3 standardized, sem teto — `runs/sweep_8b_standardized/lam=3.txt`

> that every storm had been caused by someone shouting too loudly at himself.

A frase mais surpreendente de todas as rodadas — e logo depois dela a
trajetória colapsou para exercício de tradução em chinês (o modelo
reinterpretou a frase surreal como matéria de aula). O par
frase-genial/colapso-de-gênero é o argumento empírico do teto de entropia.
