import World.Base

namespace P3.CAL3_R_F76437525B190ECB
open Mark

def VisibleStatement : Prop :=
  ∀ (p s : List Mark),
    ¬ Related (p ++ [a, a, b, b, b, a] ++ s) (p ++ [b, a, a, b, a, b] ++ s)

end P3.CAL3_R_F76437525B190ECB
