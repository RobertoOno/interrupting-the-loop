import World.Base

namespace P3.DEV_REPRESENTATION_V3
open Mark

def VisibleStatement : Prop :=
  ∀ (p s : List Mark),
    ¬ Related (p ++ [a, a, b, b] ++ s) (p ++ [a, b, a, b] ++ s)

end P3.DEV_REPRESENTATION_V3
