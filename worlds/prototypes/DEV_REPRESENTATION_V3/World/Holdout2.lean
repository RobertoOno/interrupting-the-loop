import World.Base

namespace P3.DEV_REPRESENTATION_V3
open Mark

def Holdout2Statement : Prop :=
  ∀ (p s : List Mark),
    ¬ Related (p ++ [a, a, a, b, b, b] ++ s) (p ++ [a, b, a, b, a, b] ++ s)

end P3.DEV_REPRESENTATION_V3
