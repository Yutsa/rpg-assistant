(ns rpg-assistant-web.utils.bbox-test
  (:require [cljs.test :refer [deftest is]]
            [rpg-assistant-web.utils.bbox :as bbox]))

(deftest bbox->viewport-scales-from-page-width
  (let [rect (bbox/bbox->viewport {:x0 10 :y0 20 :x1 110 :y1 40}
                                  595 595)]
    (is (= 10 (:left rect)))
    (is (= 20 (:top rect)))
    (is (= 100 (:width rect)))
    (is (= 20 (:height rect)))))

(deftest bbox->viewport-scales-to-image-width
  (let [rect (bbox/bbox->viewport {:x0 0 :y0 0 :x1 595 :y1 842}
                                  595 298)]
    (is (= 298 (:width rect)))
    (is (< (Math/abs (- 421.7075630252101 (:height rect))) 0.001))))
