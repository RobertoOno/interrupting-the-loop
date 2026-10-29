import World.Base

namespace P3.CAL3_R_F76437525B190ECB
open Mark

def Holdout2Statement : Prop :=
  ∀ (p s : List Mark),
    ¬ Related (p ++ [a, a, b, b, a, b, a, b] ++ s) (p ++ [b, a, a, a, b, b, b, a] ++ s)

end P3.CAL3_R_F76437525B190ECB
