(ns rpg.ingest.stat-blocks.cof2
  (:require [clojure.string :as str]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.stat-blocks.core :as core]
            [rpg.ingest.stat-blocks.text-utils :as tu]))

(def ^:private nc-re #"(?i)\|\s*NC\s*(\d+)")
(def ^:private name-nc-re #"(?im)^(.+?)\s*\|\s*NC\s*(\d+)\s*$")
(def ^:private stats-line-re #"(?i)\b(AGI|FOR|CON|INT|PER|CHA|VOL)\s*([+-])\s*(\d+)")
(def ^:private stats-line-start-re #"(?i)^(AGI|FOR|CON|INT|PER|CHA|VOL)\s*[+-]?\s*\d")
(def ^:private stat-block-body-re
  #"(?i)\b(DEF|PV|Init|PM)\b|Voie de|Voir le profil|Utilisez le profil")
(def ^:private stat-attack-line-re #"(?i)^(Morsure|Griffes|.+ \+\d+|.+ · DM)")
(def ^:private stat-ability-hint-re
  #"(?i)\b(DM\b|round de combat|premier round|surprise|d20|Lorsque la créature réussit)")
(def ^:private rulebook-profile-patterns
  [#"(?i)Voir le profil de (.+?) \((?:Livre de règles, )?COF\)"
   #"(?i)Utilisez le profil du?\s+(.+?)\s+que vous trouverez dans le livre de règles de COF"])
(def ^:private apostrophe-chars "'\u2019")
(def ^:private ability-title-re
  (re-pattern
   (str "^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\\s\\-" apostrophe-chars
        "]+?)\\s*(?:\\([A-Z]\\))?\\s*:\\s*(.*)$")))
(def ^:private inline-ability-title-re
  (re-pattern
   (str "(?<![A-Za-zÀ-ÿ])(?<![DdLl][" apostrophe-chars
        "])([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\\s\\-" apostrophe-chars
        "]+?)\\s*(?:\\([A-Z]\\))?\\s*:\\s*")))
(def ^:private inline-ability-skip-re
  #"(?i)\b(AGI|FOR|CON|INT|PER|CHA)\s*[+-]|\b(DEF|PV|NC|TAILLE|CRÉATURE|HUMAINE|HUMAIN)\b")
(def ^:private all-caps-name-re
  #"^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-,'\.]{1,58}$")
(def ^:private cof-attributes #{"AGI" "FOR" "CON" "INT" "PER" "CHA" "VOL"})
(def ^:private type-label-words
  #{"HUMAINE" "HUMAIN" "MORT-VIVANT" "MORT-VIVANTS" "MORT VIVANT"
    "ANIMAUX" "ANIMAL" "CONSTRUCT" "ESPRIT"})
(def ^:private chapter-re #"(?i)^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b")
(def ^:private numbered-heading-re #"^(\d+(?:\.\d+)*)\s+(.+)$")
(def ^:private list-item-marker-re #"^[\u2022\u25a0\uf0af]")

(def ^:private ability-body-patterns
  [[#"(?i)Au premier round de combat" "EMBUSCADE"]
   [#"(?i)premier round de combat" "EMBUSCADE"]
   [#"(?i)cible doit faire un test de PER difficulté 19" "EMBUSCADE"]
   [#"(?i)Lorsque la créature réussit une attaque" "DÉVORER"]
   [#"(?i)un résultat de 15-20 au d20" "DÉVORER"]])

(defn- normalized [block] (tu/strip-layout-glyphs (:text block)))

(defn- string-uppercase? [^String s]
  (and (seq s) (= s (.toUpperCase s))))

(defn- has-nc? [text] (boolean (re-find nc-re (tu/strip-layout-glyphs text))))

(defn- is-stats-line? [text]
  (let [normalized (tu/strip-layout-glyphs text)]
    (and (seq normalized)
         (>= (count (re-seq stats-line-re normalized)) 2))))

(defn- is-icon-block? [block]
  (or (= "icon" (get-in block [:metadata :stat-block-role]))
      (and (tu/has-icon-glyphs? (:text block))
           (not (seq (tu/strip-layout-glyphs (:text block)))))))

(defn- is-type-label? [text]
  (contains? type-label-words (-> text str/trim str/upper-case)))

(defn- is-icon-prefixed-name? [block]
  (and (tu/has-icon-glyphs? (:text block))
       (let [text (normalized block)]
         (and (seq text)
              (not (ro/is-page-number-label? text))
              (or (re-matches all-caps-name-re text) (has-nc? text))))))

(defn- is-stat-header-block? [block page-blocks idx]
  (cond
    (is-icon-prefixed-name? block) true
    :else
    (let [text (normalized block)]
      (cond
        (or (not (seq text)) (ro/is-page-number-label? text)) false
        (has-nc? text) true
        (is-stats-line? text) false
        (and (re-matches stats-line-start-re text) (is-stats-line? text)) false
        (is-type-label? text) false
        :else
        (when-let [next-block (nth page-blocks (inc idx) nil)]
          (when (is-stats-line? (normalized next-block))
            (let [candidate text]
              (cond
                (is-type-label? candidate) false
                (or (re-matches all-caps-name-re candidate)
                    (str/includes? candidate ",")) true
                (and (ro/block-bold? block) (string-uppercase? candidate)) true
                :else false))))))))

(defn- is-ability-block? [block]
  (let [text (normalized block)]
    (cond
      (or (not (seq text)) (is-stats-line? text) (has-nc? text)) false
      :else
      (let [first-line (first (str/split-lines text))]
        (or (re-matches stat-attack-line-re first-line)
            (and (re-find stat-ability-hint-re text) (ro/block-bold? block))
            (and (str/includes? text ":")
                 (or (re-matches ability-title-re first-line)
                     (and (ro/block-bold? block)
                          (.endsWith ^String (str/trimr first-line) ":")))))))))

(defn- extract-rulebook-reference [text]
  (let [normalized (str/replace (tu/strip-layout-glyphs text) #"\s+" " ")]
    (some (fn [pattern]
            (when-let [m (re-find pattern normalized)]
              {:profile-name (str/trim (second m))
               :source-label "Livre de règles, COF"}))
          rulebook-profile-patterns)))

(defn- normalize-ability-title [title]
  (-> title (str/replace "\u2019" "'") (str/replace "\u2018" "'") str/trim))

(defn- regex-matches [pattern text]
  (let [matcher (re-matcher pattern text)]
    (loop [acc []]
      (if (.find matcher)
        (recur (conj acc {:start (.start matcher)
                          :end (.end matcher)
                          :group1 (.group matcher 1)}))
        acc))))

(defn- parse-ability-heuristics [text]
  (let [normalized (tu/strip-layout-glyphs text)]
    (when (seq normalized)
      (let [lines (filter seq (map str/trim (str/split-lines normalized)))
            abilities (atom [])]
        (when (and (seq lines) (re-matches stat-attack-line-re (first lines)))
          (let [attack-title (str/trim (first (str/split (first lines) #"·" 2)))
                attack-body (str/trim (str/join "\n" (rest lines)))]
            (swap! abilities conj {:title attack-title :text attack-body})))
        (doseq [[pattern title] ability-body-patterns]
          (when-let [m (first (regex-matches pattern normalized))]
            (when-not (some #(= title (:title %)) @abilities)
              (swap! abilities conj {:title title :text (str/trim (subs normalized (:start m)))}))))
        @abilities))))

(defn- parse-ability-block [text]
  (let [lines (filter seq (map str/trim (str/split-lines (tu/strip-layout-glyphs text))))]
    (when (seq lines)
      (when-let [m (re-matches ability-title-re (first lines))]
        (let [title (normalize-ability-title (second m))]
          (when (and (seq title) (not (re-find inline-ability-skip-re title)))
            (let [inline-body (str/trim (nth m 2))
                  body-parts (cond-> []
                               (seq inline-body) (conj inline-body)
                               true (into (rest lines)))]
              {:title title :text (str/trim (str/join "\n" body-parts))})))))))

(defn- parse-abilities-from-inline-text [text]
  (let [normalized (tu/strip-layout-glyphs text)
        init-match (re-matcher #"(?i)\(I\)\s*Init\." normalized)]
    (let [search-text (if (.find init-match)
                        (subs normalized (.end init-match))
                        normalized)
          matches (regex-matches inline-ability-title-re search-text)]
      (vec
       (for [[idx m] (map-indexed vector matches)
             :let [title (normalize-ability-title (:group1 m))]
             :when (and (seq title) (not (re-find inline-ability-skip-re title)))]
         (let [body-start (:end m)
               body-end (if (< (inc idx) (count matches))
                          (:start (nth matches (inc idx)))
                          (count search-text))]
           {:title title :text (str/trim (subs search-text body-start body-end))}))))))

(defn- is-ability-body-continuation? [block previous]
  (and previous
       (= "ability" (get-in previous [:metadata :stat-block-role]))
       (let [text (normalized block)]
         (and (seq text)
              (not (ro/block-bold? block))
              (not (is-stats-line? text))
              (not (has-nc? text))
              (not (is-ability-block? block))
              (not (re-matches list-item-marker-re text))
              (<= (count text) 400)))))

(defn- is-stat-continuation? [block page-blocks block-idx]
  (cond
    (and page-blocks block-idx (is-stat-header-block? block page-blocks block-idx)) false
    :else
    (let [text (normalized block)]
      (cond
        (not (seq text)) false
        (is-type-label? text) true
        (is-stats-line? text) true
        (is-ability-block? block) true
        (re-find stat-block-body-re text) true
        (has-nc? text) false
        (#{"stats" "ability" "body"} (get-in block [:metadata :stat-block-role])) true
        (and (<= (count text) 200) (ro/block-bold? block)
             (or (str/includes? text ":")
                 (re-find stat-attack-line-re text)
                 (re-find stat-ability-hint-re text))) true
        (re-matches #"^\d+ pour" text) true
        (and (.endsWith ^String text ")") (<= (count text) 40)) true
        :else (and (<= (count text) 120)
                   (not (re-matches chapter-re text))
                   (not (re-matches numbered-heading-re text)))))))

(defn- is-real-section-heading? [block]
  (let [text (tu/strip-layout-glyphs (:text block))]
    (or (re-matches chapter-re text)
        (and (re-matches numbered-heading-re text) (ro/block-bold? block)))))

(defn- is-callout-interrupt-block? [block]
  (let [text (normalized block)]
    (and (seq text)
         (ro/block-bold? block)
         (string-uppercase? (.replace text "\n" " "))
         (<= (count (str/split text #"\s+")) 4))))

(defn- page-has-unclaimed-abilities? [blocks start-idx]
  (some is-ability-block? (subvec blocks start-idx)))

(defn- ends-stat-block? [block page-blocks idx]
  (cond
    (is-real-section-heading? block) true
    (is-icon-prefixed-name? block) true
    (is-stat-header-block? block page-blocks idx) true
    (and (is-callout-interrupt-block? block)
         (page-has-unclaimed-abilities? page-blocks (inc idx))) false
    :else
    (let [text (normalized block)]
      (cond
        (or (not (seq text)) (is-ability-block? block) (is-stats-line? text)) false
        (ro/block-bold? block)
        (let [font (or (get-in block [:metadata :max-font-size]) 0.0)]
          (and (>= font 12.0)
               (not (string-uppercase? text))
               (if (or (re-find stat-attack-line-re text)
                       (re-find stat-ability-hint-re text))
                 false
                 (if (re-find stat-block-body-re text)
                   false
                   (not (some is-ability-block? (subvec page-blocks (inc idx))))))))
        :else false))))

(defn- is-narrative-interrupt-block? [block page-blocks block-idx]
  (cond
    (and page-blocks block-idx (is-stat-header-block? block page-blocks block-idx)) false
    :else
    (let [text (normalized block)]
      (and (seq text)
           (not (is-ability-block? block))
           (not (is-stats-line? text))
           (not (is-icon-prefixed-name? block))
           (not (has-nc? text))
           (ro/block-bold? block)
           (not (str/includes? text ":"))
           (not (re-find stat-block-body-re text))
           (not (extract-rulebook-reference text))
           (<= (count text) 80)))))

(defn- interleave-ability-groups [left-group right-group]
  (loop [left left-group right right-group ordered [] li 0 ri 0]
    (cond
      (empty? left) (into ordered (subvec right ri))
      :else
      (let [ordered' (conj ordered (nth left li))
            [ri' ordered'']
            (if (< ri (count right))
              [(inc ri) (conj ordered' (nth right ri))]
              [ri ordered'])]
        (recur (subvec left (inc li)) right ordered'' (inc li) ri')))))

(defn- ability-blocks-in-reading-order [span page-width]
  (let [abilities (vec (filter #(= "ability" (get-in % [:metadata :stat-block-role]))
                              (:blocks span)))]
    (if (empty? abilities)
      []
      (let [layout-page {:page-number (:page-start span) :width page-width :height 1000.0}
            first-side (ro/column-side (first abilities) page-width)
            split-at (first (keep-indexed
                             (fn [idx b]
                               (when (not= (ro/column-side b page-width) first-side)
                                 idx))
                             abilities))]
        (if split-at
          (let [leading (subvec abilities 0 split-at)
                trailing (subvec abilities split-at)
                leading' (vec (sort-by #(ro/column-major-sort-key layout-page %) leading))
                trailing' (vec (sort-by #(ro/column-major-sort-key layout-page %) trailing))]
            (if (and (= first-side "right")
                     (= "left" (ro/column-side (first trailing') page-width))
                     (< (count trailing') (count leading')))
              (interleave-ability-groups trailing' leading')
              (into trailing' leading')))
          (vec (sort-by #(ro/column-major-sort-key layout-page %) abilities)))))))

(defn- update-block-at [pages page-num block-idx f]
  (mapv (fn [page]
          (if (= (:page-number page) page-num)
            (update page :blocks
                    (fn [blocks]
                      (mapv (fn [b]
                              (if (= (:block-index b) block-idx) (f b) b))
                            blocks)))
            page))
        pages))

(defn- tag-block [pages page-num block span-id role]
  (update-block-at pages page-num (:block-index block)
                   (fn [b]
                     (-> b
                         (assoc-in [:metadata :stat-block-id] span-id)
                         (assoc-in [:metadata :stat-block-role] role)))))

(defn- with-page-number [block page-num]
  (assoc block :page-number page-num))

(defn- span-entry [block page-num role]
  (-> block
      (with-page-number page-num)
      (assoc-in [:metadata :stat-block-role] role)))

(defn- flush-span [spans span-id span-blocks]
  (if (seq span-blocks)
    (let [page-nums (map :page-number span-blocks)]
      (conj spans {:id span-id
                   :blocks (vec span-blocks)
                   :page-start (apply min page-nums)
                   :page-end (apply max page-nums)}))
    spans))

(defn- detect-spans-on-pages [pages]
  (let [pages' (mapv (fn [page]
                         (update page :blocks
                                 (fn [blocks]
                                   (->> blocks
                                        (sort-by #(ro/column-major-sort-key page %))
                                        vec
                                        ro/reindex-blocks))))
                     pages)]
    (letfn [(process-page [pages spans page pending-icons]
              (loop [pages pages
                     idx 0
                     pending pending-icons
                     spans spans
                     span-blocks []
                     span-id nil]
                (if (>= idx (count (:blocks page)))
                  {:pages pages :spans spans}
                  (let [page-num (:page-number page)
                        blocks (:blocks page)
                        block (nth blocks idx)]
                    (cond
                      (is-icon-block? block)
                      (if (and span-id
                               (some #(= "header" (get-in % [:metadata :stat-block-role])) span-blocks))
                        (let [pages' (tag-block pages page-num block span-id "icon")]
                          (recur pages' (inc idx) [block] (flush-span spans span-id span-blocks) [] nil))
                        (recur pages (inc idx) (conj pending block) spans span-blocks span-id))

                      (or (is-stat-header-block? block blocks idx)
                          (and (seq pending)
                               (let [first-line (str/trim (first (str/split-lines (normalized block))))
                                     name-line (str/trim (first (str/split first-line #"\|" 2)))]
                                 (and (seq name-line)
                                      (re-matches all-caps-name-re name-line)
                                      (not (ro/is-meta-box-heading? name-line))))))
                      (let [new-span-id (ids/new-id "sb")
                            pages' (reduce #(tag-block %1 page-num %2 new-span-id "icon") pages pending)
                            span-blocks' (mapv #(span-entry % page-num "icon") pending)]
                        (if (and (pos? idx)
                                 (not (get-in (nth blocks (dec idx)) [:metadata :stat-block-id])))
                          (let [prev (nth blocks (dec idx))
                                prev-text (normalized prev)
                                header-text (normalized block)]
                            (if (and (seq prev-text) (str/includes? header-text prev-text))
                              (recur (tag-block (tag-block pages' page-num prev new-span-id "header")
                                                page-num block new-span-id "header")
                                     (inc idx) []
                                     spans
                                     (-> span-blocks'
                                         (conj (span-entry prev page-num "header"))
                                         (conj (span-entry block page-num "header")))
                                     new-span-id)
                              (recur (tag-block pages' page-num block new-span-id "header")
                                     (inc idx) []
                                     spans
                                     (conj span-blocks' (span-entry block page-num "header"))
                                     new-span-id)))
                          (recur (tag-block pages' page-num block new-span-id "header")
                                 (inc idx) []
                                 spans
                                 (conj span-blocks' (span-entry block page-num "header"))
                                 new-span-id)))

                      span-id
                      (cond
                        (ends-stat-block? block blocks idx)
                        (if (and (is-callout-interrupt-block? block)
                                 (not (is-stat-header-block? block blocks idx)))
                          (recur pages (inc idx) pending spans span-blocks span-id)
                          (recur pages idx pending (flush-span spans span-id span-blocks) [] nil))

                        (is-stats-line? (normalized block))
                        (recur (tag-block pages page-num block span-id "stats")
                               (inc idx) pending spans
                               (conj span-blocks (span-entry block page-num "stats"))
                               span-id)

                        (is-ability-block? block)
                        (recur (tag-block pages page-num block span-id "ability")
                               (inc idx) pending spans
                               (conj span-blocks (span-entry block page-num "ability"))
                               span-id)

                        (is-ability-body-continuation? block (last span-blocks))
                        (recur (tag-block pages page-num block span-id "ability")
                               (inc idx) pending spans
                               (conj span-blocks (span-entry block page-num "ability"))
                               span-id)

                        (and (is-narrative-interrupt-block? block blocks idx)
                             (some is-ability-block? (subvec blocks (inc idx))))
                        (recur pages (inc idx) pending spans span-blocks span-id)

                        (and (seq span-blocks) (is-stat-continuation? block blocks idx))
                        (recur (tag-block pages page-num block span-id "body")
                               (inc idx) pending spans
                               (conj span-blocks (span-entry block page-num "body"))
                               span-id)

                        :else
                        (recur pages idx pending (flush-span spans span-id span-blocks) [] nil))

                      :else
                      (recur pages (inc idx) pending spans span-blocks span-id))))))]
      (loop [pages pages' spans [] page-idx 0 pending []]
        (if (>= page-idx (count pages))
          {:pages pages :spans spans}
          (let [page (nth pages page-idx)
                {:keys [pages spans]} (process-page pages spans page pending)]
            (recur pages spans (inc page-idx) [])))))))

(defmethod core/matches-document? :cof2 [_ pages]
  (let [counts (reduce
                (fn [acc block]
                  (let [text (tu/strip-layout-glyphs (:text block))]
                    (-> acc
                        (cond-> (has-nc? text) (update :nc-count inc))
                        (cond-> (is-stats-line? text) (update :stats-count inc)))))
                {:nc-count 0 :stats-count 0}
                (mapcat :blocks pages))]
    (and (pos? (:nc-count counts)) (pos? (:stats-count counts)))))

(defmethod core/false-heading? :cof2 [_ block page-blocks idx _page]
  (let [role (get-in block [:metadata :stat-block-role])
        text (normalized block)]
    (cond
      (#{"header" "stats" "icon"} role) true
      (or (not (seq text)) (ro/is-page-number-label? text)) false
      (has-nc? text) true
      (is-stats-line? text) true
      (is-icon-block? block) true
      (is-icon-prefixed-name? block) true
      (is-type-label? text) true
      :else (is-stat-header-block? block page-blocks idx))))

(defmethod core/detect-spans :cof2 [_ pages]
  (detect-spans-on-pages pages))

(defmethod core/normalize-block-text :cof2 [_ text]
  (tu/strip-layout-glyphs text))

(defmethod core/parse-span :cof2 [_ span]
  (let [texts (mapv #(tu/strip-layout-glyphs (:text %)) (:blocks span))
        combined (str/join "\n\n" (filter seq texts))
        parsed (atom {:name "" :subtitle nil :nc nil :attributes {} :abilities []})
        page-width (* (apply max 0 (map #(get-in % [:bbox :x1]) (:blocks span))) 1.2)]
    (doseq [text texts]
      (when (seq text)
        (when-let [header-match (re-find name-nc-re text)]
          (let [header-part (str/trim (nth header-match 1))]
            (swap! parsed assoc :nc (Integer/parseInt (nth header-match 2)))
            (if (str/includes? header-part ",")
              (let [[name-part sub-part] (str/split header-part #"," 2)]
                (swap! parsed assoc :name (str/trim name-part) :subtitle (str/trim sub-part)))
              (swap! parsed assoc :name header-part))))
        (when-let [nc-line (first (filter #(re-find #"(?i)\|\s*NC\s*\d+" %) (str/split-lines text)))]
          (when-let [m (re-find #"(?i)\|\s*NC\s*(\d+)\s+(.+)$" (str/trim nc-line))]
            (swap! parsed assoc :nc (Integer/parseInt (second m)))
            (let [header-part (str/trim (nth m 2))]
              (when (str/includes? header-part ",")
                (let [[name-part sub-part] (str/split header-part #"," 2)]
                  (swap! parsed assoc :name (str/trim name-part) :subtitle (str/trim sub-part))))
              (when-not (seq (:name @parsed))
                (swap! parsed assoc :name (str/trim (first (str/split header-part #","))))))))
        (doseq [[_ attr sign value] (re-seq stats-line-re text)]
          (let [key (str/upper-case attr)]
            (when (contains? cof-attributes key)
              (swap! parsed assoc-in [:attributes (keyword key)]
                     (if (= sign "+") (Integer/parseInt value) (- (Integer/parseInt value)))))))))
    (doseq [[_ attr sign value] (re-seq stats-line-re combined)]
      (let [key (str/upper-case attr)]
        (when (contains? cof-attributes key)
          (swap! parsed assoc-in [:attributes (keyword key)]
                 (if (= sign "+") (Integer/parseInt value) (- (Integer/parseInt value)))))))
    (doseq [block (ability-blocks-in-reading-order span page-width)]
      (let [text (tu/strip-layout-glyphs (:text block))
            ability (or (parse-ability-block text)
                        (some identity
                              (for [a (parse-ability-heuristics text)
                                    :when (and (:title a)
                                               (not (re-find #"^(?i)(Masse|Équipement)\b" (:title a))))]
                                a)))]
        (when (and ability
                   (not (some #(= (:title ability) (:title %)) (:abilities @parsed))))
          (swap! parsed update :abilities conj ability))))
    (let [inline (parse-abilities-from-inline-text combined)
          abilities (:abilities @parsed)
          use-inline? (or (empty? abilities)
                          (< (count abilities) (count inline))
                          (some #(empty? (:text %)) abilities))]
      (when use-inline?
        (swap! parsed assoc :abilities [])
        (doseq [ability inline]
          (swap! parsed update :abilities conj ability)))
      (when-not use-inline?
        (doseq [ability inline]
          (when-not (some #(= (:title ability) (:title %)) (:abilities @parsed))
            (swap! parsed update :abilities conj ability))))
      (doseq [ability (or (parse-ability-heuristics combined) [])]
        (when-not (some #(= (:title ability) (:title %)) (:abilities @parsed))
          (swap! parsed update :abilities conj ability))))
    (when-not (seq (:name @parsed))
      (doseq [text texts]
        (let [candidate (str/trim (first (str/split-lines text)))]
          (when (and (seq candidate)
                     (re-matches all-caps-name-re candidate)
                     (not (is-stats-line? candidate))
                     (not (re-find #"(?i)^(DEF|PV|Init|PM)\b" candidate)))
            (swap! parsed assoc :name (-> candidate (str/split #",") first str/trim))))))
    (let [p @parsed
          block-refs (mapv (fn [b] {:page-number (:page-number b)
                                    :block-index (:block-index b)})
                           (:blocks span))]
      (cond-> (assoc p
                     :raw-text combined
                     :block-refs block-refs
                     :game-system "cof2")
        (extract-rulebook-reference combined)
        (assoc :rulebook-reference (extract-rulebook-reference combined))))))

(defmethod core/chunk-type-hint :cof2 [_ text blocks]
  (cond
    (some #(get-in % [:metadata :stat-block-id]) blocks) "stat_block"
    (let [normalized (tu/strip-layout-glyphs text)]
      (or (has-nc? normalized) (is-stats-line? normalized))) "stat_block"
    :else nil))
