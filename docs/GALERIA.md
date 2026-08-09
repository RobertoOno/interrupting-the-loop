# Galeria — artefatos selecionados

> O que a máquina já produziu que valeu guardar. Cada peça com proveniência
> completa (modelo, parâmetros, seed) para reprodução. Seleção manual por ora;
> o loop de seleção (item 6 do roadmap) automatizará o funil.

Modelo de todas as peças: `Qwen3-8B-Base-8bit` (quantização local), prompt
`"The lighthouse keeper had one theory about the sea, and it was this:"`,
seed 0, temperatura 1.0, piso 0.05, meia-vida 16.

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
