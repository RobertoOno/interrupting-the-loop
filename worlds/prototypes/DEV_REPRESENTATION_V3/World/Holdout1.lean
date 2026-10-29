import World.Base

namespace P3.DEV_REPRESENTATION_V3
open Mark

def Holdout1Statement : Prop :=
  ∀ (p s : List Mark),
    ¬ Related (p ++ [a, b, b, a] ++ s) (p ++ [b, a, a, b] ++ s)

end P3.DEV_REPRESENTATION_V3
