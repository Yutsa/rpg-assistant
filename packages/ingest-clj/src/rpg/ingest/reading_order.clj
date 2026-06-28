(ns rpg.ingest.reading-order
  "Ordre de lecture (passe 1) et utilitaires typo/géométrie (passe 2)."
  (:require [clojure.string :as str]))

(def ^:private min-column-overlap 0.35)
(def ^:private narrow-box-max-width 160.0)
(def ^:private narrow-box-x-margin 35.0)
(def ^:private narrow-box-max-vertical-gap 130.0)
(def ^:private decorative-font-ratio 2.0)
(def ^:private decorative-min-font 28.0)
(def ^:private decorative-top-ratio 0.33)
(def ^:private vertical-header-max-width 20.0)
(def ^:private vertical-header-min-x-ratio 0.85)
(def ^:private title-case-max-words 6)
(def ^:private title-case-min-words 2)
(def ^:private conditional-hook-max-words 10)
(def ^:private caps-subordinate-max-gap 80.0)

(def max-subordinate-chapter-page-gap 3)

(def ^:private page-banner-prefixes
  ["INTRODUCTION" "IMPLICATION" "CONCLUSION"])

(def ^:private meta-box-headings
  #{"CRÉDITS" "EN QUELQUES MOTS" "FICHE TECHNIQUE"})

(def ^:private editorial-credits-markers
  ["black book" "tous droits réservés" "tous droits reserves"])

(def ^:private all-caps-re
  #"^[A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ\s\-:,'\.]{2,}$")

(def ^:private title-case-word-re
  #"(?u)^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][\w'\u2019\-]+(?:\s+(?:[a-zàâäéèêëïîôùûüÿç][\w'\u2019\-]+|[A-Z]{2,})){1,5}$")

(def ^:private page-number-label-re
  #"(?i)^PAGE\s+\d+\s*$")

(def ^:private chapter-re
  #"(?i)^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b")

(def ^:private list-item-marker-re
  #"^[\u0090-\u0095\u2022\u25AA-\u25C6\u25E6\-–—]\s*")

(def ^:private list-item-name-re
  #"(?u)^[\wÀ-ÿ][\wÀ-ÿ\s'\-]{0,40}\u202f:")

(def ^:private numbered-heading-re
  #"^(\d+(?:\.\d+)*)\s+(.+)$")

(def ^:private table-row-label-re
  #"^[A-Z]-\d+$")

(def ^:private conditional-hook-re
  #"(?i)^Si\s+")

(defn spatial-sort-key
  "Tri générique : position horizontale puis verticale."
  [block]
  [(get-in block [:bbox :x0])
   (get-in block [:bbox :y0])
   (get-in block [:bbox :x1])])

(defn sort-blocks-spatial
  [blocks]
  (vec (sort-by spatial-sort-key blocks)))

(defn reindex-blocks
  "Réattribue :block-index 0..n dans l'ordre de la liste."
  [blocks]
  (vec (map-indexed (fn [idx block] (assoc block :block-index idx)) blocks)))

(defn normalize-page-blocks
  "Trie les blocs en ordre spatial et ré-indexe."
  [blocks]
  (-> blocks sort-blocks-spatial reindex-blocks))

(defn normalize-page
  [page]
  (update page :blocks normalize-page-blocks))

(defn normalize-reading-order
  "Applique le tri spatial sur chaque page."
  [pages]
  (mapv normalize-page pages))

(defn spatial-ordered?
  "Vérifie qu'une liste de blocs respecte l'ordre (x0, y0, x1)."
  [blocks]
  (every? true?
          (map (fn [[prev cur]]
                 (neg? (compare (spatial-sort-key prev) (spatial-sort-key cur))))
               (partition 2 1 blocks))))

(defn horizontal-overlap-ratio
  "Ratio de chevauchement horizontal (plus étroit / overlap) — pour passe 2."
  [left right]
  (let [overlap (- (min (get-in left [:bbox :x1]) (get-in right [:bbox :x1]))
                   (max (get-in left [:bbox :x0]) (get-in right [:bbox :x0])))]
    (if (<= overlap 0)
      0.0
      (let [narrower (min (- (get-in left [:bbox :x1]) (get-in left [:bbox :x0]))
                          (- (get-in right [:bbox :x1]) (get-in right [:bbox :x0])))]
        (if (<= narrower 0)
          0.0
          (/ overlap narrower))))))

(defn is-in-column-band?
  "Deux blocs partagent-ils la même bande horizontale (fils de lecture parallèles)."
  ([block heading]
   (is-in-column-band? block heading min-column-overlap))
  ([block heading min-overlap]
   (>= (horizontal-overlap-ratio block heading) min-overlap)))

(defn same-reading-stream?
  "Même fil de lecture que le bloc de référence."
  [ref-block block]
  (is-in-column-band? block ref-block))

(defn block-x-cluster
  "Cluster x grossier (x0) pour assertions de test."
  [block]
  (get-in block [:bbox :x0]))

(defn- layout-char? [c]
  (let [ch (char (int c))
        t (Character/getType ch)]
    (or (= t Character/FORMAT)
        (= t Character/PRIVATE_USE)
        (= t Character/SURROGATE))))

(defn strip-glyphs
  [text]
  (->> text
       (remove layout-char?)
       (apply str)
       str/trim))

(defn block-max-font
  [block]
  (double (or (get-in block [:metadata :max-font-size])
              (get-in block [:metadata :max_font_size])
              0.0)))

(defn block-bold?
  [block]
  (boolean (or (get-in block [:metadata :is-bold])
               (get-in block [:metadata :is_bold]))))

(defn column-side
  [block page-width]
  (let [center (/ (+ (get-in block [:bbox :x0]) (get-in block [:bbox :x1])) 2.0)]
    (if (< center (/ page-width 2.0)) "left" "right")))

(defn column-major-sort-key
  [page block]
  (let [side (if (= "left" (column-side block (:width page))) 0 1)]
    [(:page-number page) side (get-in block [:bbox :y0]) (get-in block [:bbox :x0])]))

(defn page-median-font
  [blocks]
  (let [sizes (->> blocks
                   (map block-max-font)
                   (filter pos?)
                   sort
                   vec)]
    (if (empty? sizes)
      12.0
      (let [mid (quot (count sizes) 2)]
        (if (odd? (count sizes))
          (nth sizes mid)
          (/ (+ (nth sizes (dec mid)) (nth sizes mid)) 2.0))))))

(defn is-decorative-spread-title?
  [block page median-font]
  (let [text (strip-glyphs (:text block))
        max-font (block-max-font block)]
    (and (seq text)
         (re-matches all-caps-re text)
         (or (>= max-font decorative-min-font)
             (>= max-font (* median-font decorative-font-ratio)))
         (<= (get-in block [:bbox :y0]) (* (:height page) decorative-top-ratio))
         (<= (count (str/split text #"\s+")) 4)
         (<= (count (str/split text #"\n")) 2))))

(defn- spread-title-vertical-gap [upper lower]
  (- (get-in lower [:bbox :y0]) (get-in upper [:bbox :y1])))

(defn is-spread-title-pair?
  [upper lower page median-font]
  (let [lower-text (strip-glyphs (:text lower))
        gap (spread-title-vertical-gap upper lower)]
    (and (is-decorative-spread-title? upper page median-font)
         (seq lower-text)
         (re-matches all-caps-re lower-text)
         (<= (get-in lower [:bbox :y0]) (* (:height page) decorative-top-ratio))
         (<= gap 8.0)
         (>= gap -30.0)
         (<= (count (str/split lower-text #"\s+")) 4))))

(defn is-vertical-running-header?
  [block page]
  (let [width (- (get-in block [:bbox :x1]) (get-in block [:bbox :x0]))
        text (strip-glyphs (:text block))]
    (and (<= width vertical-header-max-width)
         (>= (get-in block [:bbox :x0]) (* (:width page) vertical-header-min-x-ratio))
         (seq text)
         (<= (count text) 80)
         (<= (count (str/split text #"\s+")) 12))))

(defn is-page-number-label?
  [text]
  (boolean (re-matches page-number-label-re (strip-glyphs text))))

(defn is-page-banner-heading?
  [text block page]
  (let [cleaned (strip-glyphs text)
        first-line (-> cleaned (str/split #"\n") first str/trim)
        upper (str/upper-case first-line)
        letters (filter #(Character/isLetter ^char %) first-line)]
    (and (seq cleaned)
         (some #(str/starts-with? upper %) page-banner-prefixes)
         (<= (get-in block [:bbox :y0]) (* (:height page) decorative-top-ratio))
         (seq letters)
         (>= (/ (count (filter #(Character/isUpperCase ^char %) letters))
               (count letters))
             0.8))))

(defn is-conditional-hook-heading?
  [text block median-font]
  (let [cleaned (strip-glyphs text)
        max-font (block-max-font block)]
    (and (seq cleaned)
         (re-matches conditional-hook-re cleaned)
         (<= (count (str/split cleaned #"\s+")) conditional-hook-max-words)
         (block-bold? block)
         (< max-font (* median-font 1.5))
         (>= max-font (* median-font 1.05)))))

(defn is-title-case-heading?
  [text block median-font]
  (let [cleaned (-> text strip-glyphs (str/split #"\s+") (->> (str/join " ")))
        max-font (block-max-font block)
        words (str/split cleaned #"\s+")]
    (when (and (seq cleaned) (block-bold? block) (>= max-font (* median-font 1.05)))
      (cond
        (is-conditional-hook-heading? text block median-font) true
        (= 1 (count words))
        (and (block-bold? block)
             (>= max-font (* median-font 1.05))
             (Character/isUpperCase ^char (first cleaned))
             (some #(Character/isLowerCase ^char %) (subs cleaned 1)))
        (<= title-case-min-words (count words) title-case-max-words)
        (boolean (re-matches title-case-word-re cleaned))
        :else false))))

(defn is-meta-box-heading?
  [text]
  (contains? meta-box-headings (str/upper-case (strip-glyphs text))))

(defn is-reward-box-heading?
  [text]
  (let [normalized (-> text strip-glyphs (str/split #"\s+") (->> (str/join " ")) str/upper-case)]
    (or (str/starts-with? normalized "RÉCOMPENSE")
        (str/starts-with? normalized "RECOMPENSE"))))

(defn is-narrow-box-heading?
  [text]
  (or (is-meta-box-heading? text) (is-reward-box-heading? text)))

(defn is-credits-heading?
  [text]
  (= (str/upper-case (strip-glyphs text)) "CRÉDITS"))

(defn is-editorial-credits-text?
  [text]
  (let [lowered (str/lower-case (strip-glyphs text))]
    (some #(str/includes? lowered %) editorial-credits-markers)))

(defn is-editorial-credits-block?
  [block]
  (is-editorial-credits-text? (:text block)))

(defn is-all-caps-heading-text?
  [text]
  (let [first-line (-> text strip-glyphs (str/split #"\n") first str/trim)]
    (boolean (re-matches all-caps-re first-line))))

(defn normalize-section-title
  [text]
  (let [stripped (strip-glyphs text)]
    (if (and (str/includes? stripped "\n") (is-all-caps-heading-text? stripped))
      (str/join " " (str/split stripped #"\s+"))
      stripped)))

(defn is-chapter-heading?
  [text]
  (boolean (re-find chapter-re (strip-glyphs text))))

(defn is-list-item-block?
  [block]
  (let [text (strip-glyphs (:text block))]
    (cond
      (not (seq text)) false
      (re-find list-item-marker-re text) true
      (and (block-bold? block) (<= (count (str/split text #"\s+")) 6)) false
      (and (re-matches list-item-name-re text) (<= (count text) 80)) true
      :else false)))

(defn heading-visual-tier
  "Classifie le style : meta, chapter, banner, subordinate, other."
  [text block {:keys [median-font page]}]
  (cond
    (is-meta-box-heading? text) "meta"
    (and page (is-page-banner-heading? text block page)) "banner"
    (is-chapter-heading? text) "chapter"
    (is-title-case-heading? text block median-font) "subordinate"
    :else "other"))

(defn is-drop-cap-false-heading?
  [block page-blocks block-idx]
  (let [text (str/trim (:text block))]
    (and (= 1 (count text))
         (Character/isUpperCase ^char (first text))
         (< (inc block-idx) (count page-blocks))
         (let [nxt (-> (get-in page-blocks [(inc block-idx) :text]) str/trim)]
           (and (seq nxt) (Character/isLowerCase ^char (first nxt)))))))

(defn font-transition-heading?
  "Signal typo corps → titre entre blocs consécutifs."
  [block prev-block page median-font page-blocks block-idx]
  (let [text (str/trim (:text block))
        max-font (block-max-font block)
        is-bold (block-bold? block)
        prev-max (when prev-block (block-max-font prev-block))]
    (and (seq text)
         (<= (count text) 120)
         (<= (count (str/split text #"\s+")) 14)
         (not (is-drop-cap-false-heading? block page-blocks block-idx))
         (not (is-vertical-running-header? block page))
         (not (is-decorative-spread-title? block page median-font))
         (not (and prev-block
                   (is-spread-title-pair? prev-block block page median-font)))
         (or (is-chapter-heading? text)
             (is-meta-box-heading? text)
             (is-reward-box-heading? text)
             (is-title-case-heading? text block median-font)
             (and (re-matches numbered-heading-re text)
                  (or is-bold (>= max-font (* median-font 1.05))))
             (and (re-matches all-caps-re text)
                  (>= (count text) 4)
                  (>= max-font median-font))
             (and is-bold
                  (>= max-font (* median-font 1.15))
                  (<= 3 (count text) 80))
             (and prev-block
                  is-bold
                  (>= max-font (* (or prev-max max-font) 1.1))
                  (<= (count (str/split text #"\s+")) 14)
                  (<= (count text) 120))))))

(defn heading-level
  [text block median-font]
  (let [tier (heading-visual-tier text block {:median-font median-font})]
    (cond
      (#{"meta" "chapter" "banner"} tier) 1
      (= "subordinate" tier) 2
      :else (let [numbered (re-matches numbered-heading-re text)]
              (if numbered
                (min 4 (+ 1 (count (str/split (nth numbered 1) #"\."))))
                (cond
                  (>= (block-max-font block) (* median-font 1.3)) 1
                  (>= (block-max-font block) (* median-font 1.15)) 2
                  :else 3))))))

(defn find-block
  [pages page-number block-index]
  (some (fn [page]
          (when (= (:page-number page) page-number)
            (some #(when (= (:block-index %) block-index) %)
                  (:blocks page))))
        pages))

(defn same-page-caps-parent-id
  [page-num block sections anchors pages]
  (let [page (some #(when (= (:page-number %) page-num) %) pages)
        median (page-median-font (:blocks page))]
  (loop [best-id nil best-y -1.0 idx 0]
    (if (>= idx (count sections))
      best-id
      (let [section (nth sections idx)
            anchor (nth anchors idx)
            parent-block (find-block pages (first anchor) (second anchor))]
        (recur
         (if (and (= (first anchor) page-num)
                  parent-block
                  (not (#{"chapter" "banner" "meta"}
                        (heading-visual-tier (:title section) parent-block
                                             {:median-font median :page page})))
                  (is-all-caps-heading-text? (:title section))
                  (is-in-column-band? block parent-block)
                  (< (get-in parent-block [:bbox :y0]) (get-in block [:bbox :y0]))
                  (<= (- (get-in block [:bbox :y0]) (get-in parent-block [:bbox :y1]))
                      caps-subordinate-max-gap)
                  (> (get-in parent-block [:bbox :y0]) best-y))
           (:id section)
           best-id)
         (if (and parent-block (> (get-in parent-block [:bbox :y0]) best-y))
           (get-in parent-block [:bbox :y0])
           best-y)
         (inc idx)))))))
