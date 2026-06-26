(ns rpg.ingest.sections
  "Passe 2 : détection sections + affectation bloc→section."
  (:require [clojure.set :as set]
            [clojure.string :as str]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.reading-order :as ro]))

(def ^:private spatial-y-tolerance 5.0)
(def ^:private preamble-title "Introduction")
(def ^:private min-bold-heading-len 3)
(def ^:private numbered-heading-re #"^(\d+(?:\.\d+)*)\s+(.+)$")
(def ^:private table-row-label-re #"^[A-Z]-\d+$")
(def ^:private all-caps-re
  #"^[A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ\s\-:,'\.]{2,}$")

(defn- block-id [document-id page-number block-index]
  (ids/page-block-id document-id page-number block-index))

(defn- make-section
  [campaign-id document-id title level page-start page-end & {:keys [parent-section-id id]}]
  {:id (or id (ids/new-id "sec"))
   :campaign-id campaign-id
   :document-id document-id
   :parent-section-id parent-section-id
   :title title
   :level level
   :page-start page-start
   :page-end page-end})

(defn- heading-sort-key [pages page-num block-idx]
  (if-let [block (ro/find-block pages page-num block-idx)]
    (let [y-bucket (* (Math/round (/ (get-in block [:bbox :y0]) spatial-y-tolerance))
                      spatial-y-tolerance)]
      [page-num y-bucket (get-in block [:bbox :x0])])
    [page-num (double block-idx) 0.0]))

(defn- spatially-sorted-headings [headings pages]
  (vec (sort-by (fn [[page-num block-idx _ _]]
                  (heading-sort-key pages page-num block-idx))
                headings)))

(defn- heading-candidate?
  [block page median page-blocks block-idx]
  (let [text (str/trim (:text block))
        max-font (ro/block-max-font block)
        is-bold (ro/block-bold? block)]
    (and (seq text)
         (<= (count text) 120)
         (<= (count (str/split text #"\s+")) 14)
         (not (ro/is-drop-cap-false-heading? block page-blocks block-idx))
         (not (ro/is-vertical-running-header? block page))
         (not (ro/is-decorative-spread-title? block page median))
         (not (and (pos? block-idx)
                   (ro/is-spread-title-pair? (nth page-blocks (dec block-idx)) block page median)))
         (or (ro/is-chapter-heading? text)
             (ro/is-meta-box-heading? text)
             (ro/is-reward-box-heading? text)
             (ro/is-title-case-heading? text block median)
             (and (re-matches numbered-heading-re text)
                  (or is-bold (>= max-font (* median 1.05))))
             (and (re-matches all-caps-re text)
                  (>= (count text) 4)
                  (>= max-font median))
             (and is-bold
                  (>= max-font (* median 1.15))
                  (<= min-bold-heading-len (count text) 80)))
         (not (re-matches table-row-label-re (str/replace text #"\n" " "))))))

(defn- heading-level [text block median]
  (let [tier (ro/heading-visual-tier text block {:median-font median})]
    (cond
      (#{"meta" "chapter" "banner"} tier) 1
      (= "subordinate" tier) 2
      :else (if-let [numbered (re-matches numbered-heading-re text)]
              (min 4 (+ 1 (count (str/split (nth numbered 1) #"\."))))
              (cond
                (>= (ro/block-max-font block) (* median 1.3)) 1
                (>= (ro/block-max-font block) (* median 1.15)) 2
                :else 3)))))

(defn- reparent-same-page-subordinates
  [sections chapter-section-id chapter-page subordinate-ids]
  (let [by-id (into {} (map (juxt :id identity) sections))]
    (vec
     (for [section sections]
       (if (and (= (:page-start section) chapter-page)
                (not= (:id section) chapter-section-id)
                (contains? subordinate-ids (:id section)))
         (let [parent (when (:parent-section-id section)
                        (get by-id (:parent-section-id section)))]
           (if (or (nil? parent) (not= (:page-start parent) chapter-page))
             (-> section
                 (assoc :parent-section-id chapter-section-id)
                 (assoc :level 2))
             section))
         section)))))

(defn- detect-preamble-sections
  [pages heading-positions campaign-id document-id]
  (loop [preamble-sections []
         preamble-anchors []
         content-only-ids #{}
         pages-left pages]
    (if (empty? pages-left)
      {:preamble-sections preamble-sections
       :preamble-anchors preamble-anchors
       :content-only-ids content-only-ids}
      (let [page (first pages-left)
            page-num (:page-number page)
            chapter-blocks (filter #(ro/is-chapter-heading? (:text %)) (:blocks page))]
        (if (empty? chapter-blocks)
          (recur preamble-sections preamble-anchors content-only-ids (rest pages-left))
          (let [chapter-block (apply min-key #(get-in % [:bbox :y0]) chapter-blocks)
                meta-headings (filter #(and (contains? heading-positions [page-num (:block-index %)])
                                            (ro/is-meta-box-heading? (:text %)))
                                      (:blocks page))
                preamble-block
                (some
                 (fn [[block-idx block]]
                   (when (and (not (contains? heading-positions [page-num block-idx]))
                              (ro/is-in-column-band? block chapter-block)
                              (< (get-in block [:bbox :y0]) (get-in chapter-block [:bbox :y0]))
                              (not (some #(and (contains? heading-positions [page-num (:block-index %)])
                                               (ro/is-in-column-band? % chapter-block)
                                               (> (get-in % [:bbox :y0]) (get-in block [:bbox :y0]))
                                               (< (get-in % [:bbox :y0]) (get-in chapter-block [:bbox :y0])))
                                         (:blocks page)))
                              (not (ro/is-list-item-block? block))
                              (not (ro/is-editorial-credits-block? block))
                              (not (some #(and (>= (get-in block [:bbox :y0]) (get-in % [:bbox :y0]))
                                               (ro/is-meta-box-heading? (:text %))
                                               (> (get-in block [:bbox :y0]) (get-in % [:bbox :y1])))
                                         meta-headings)))
                     (let [claimed (some #(and (<= (get-in block [:bbox :y0]) (+ (get-in % [:bbox :y1]) 130))
                                               (>= (get-in block [:bbox :x0]) (- (get-in % [:bbox :x0]) 35))
                                               (<= (get-in block [:bbox :x1]) (+ (get-in % [:bbox :x1]) 35)))
                                         meta-headings)]
                       (when-not claimed [block-idx block]))))
                 (map-indexed vector (:blocks page)))]
            (if preamble-block
              (let [[block-idx _block] preamble-block
                    sec-id (ids/new-id "sec")]
                (recur (conj preamble-sections
                             (make-section campaign-id document-id preamble-title 1 page-num page-num :id sec-id))
                       (conj preamble-anchors [page-num block-idx])
                       (conj content-only-ids sec-id)
                       (rest pages-left)))
              (recur preamble-sections preamble-anchors content-only-ids (rest pages-left)))))))))

(defn- anchor-before? [a b]
  (or (< (first a) (first b))
      (and (= (first a) (first b)) (< (second a) (second b)))))

(defn- merge-preamble [sections anchors preamble-sections preamble-anchors content-only-ids]
  (if (empty? preamble-sections)
    {:sections sections :anchors anchors :content-only-ids content-only-ids}
    (let [{:keys [out-s out-a pidx]}
          (reduce
           (fn [acc [sec anc]]
             (let [{:keys [out-s out-a pidx]} acc]
               (loop [ms out-s ma out-a pi pidx]
                 (if (and (< pi (count preamble-sections))
                          (anchor-before? (nth preamble-anchors pi) anc))
                   (recur (conj ms (nth preamble-sections pi))
                          (conj ma (nth preamble-anchors pi))
                          (inc pi))
                   {:out-s (conj ms sec) :out-a (conj ma anc) :pidx pi}))))
           {:out-s [] :out-a [] :pidx 0}
           (map vector sections anchors))]
      {:sections (into out-s (subvec preamble-sections pidx))
       :anchors (into out-a (subvec preamble-anchors pidx))
       :content-only-ids content-only-ids})))

(defn- pop-stack-to-level [stack level]
  (loop [s stack]
    (if (or (empty? s) (< (first (peek s)) level))
      s
      (recur (pop s)))))

(defn- build-sections-from-headings
  [headings pages campaign-id document-id page-count page-medians]
  (loop [remaining headings
         sections []
         anchors []
         stack []
         active-chapter-id nil
         subordinate-ids #{}]
    (if (empty? remaining)
      {:sections sections :anchors anchors}
      (let [[page-num block-idx title _level-in] (first remaining)
            page (first (filter #(= (:page-number %) page-num) pages))
            block (ro/find-block pages page-num block-idx)
            median (get page-medians page-num 12.0)
            tier (if block
                   (ro/heading-visual-tier title block {:median-font median :page page})
                   "other")
            caps-parent-id (when block
                             (ro/same-page-caps-parent-id page-num block sections anchors pages))
            level (heading-level title block median)
            parent-id
            (cond
              (= tier "meta") nil
              (#{"chapter" "banner"} tier) nil
              (= tier "subordinate")
              (cond caps-parent-id
                    caps-parent-id
                    active-chapter-id
                    (let [chapter (first (filter #(= (:id %) active-chapter-id) sections))]
                      (when (and chapter
                                 (<= (- page-num (:page-start chapter))
                                     ro/max-subordinate-chapter-page-gap))
                        active-chapter-id))
                    :else nil)
              :else
              (cond
                (and caps-parent-id (not (ro/is-all-caps-heading-text? title))) caps-parent-id
                :else (when (seq stack) (second (peek stack)))))
            level'
            (cond
              (= tier "meta") 1
              (#{"chapter" "banner"} tier) 1
              (= tier "subordinate")
              (if parent-id
                (inc (:level (first (filter #(= (:id %) parent-id) sections))))
                2)
              :else level)
            page-end (if (> (count remaining) 1) (first (first (rest remaining))) page-count)
            section-id (ids/new-id "sec")
            section (make-section campaign-id document-id
                                  (ro/normalize-section-title title)
                                  level' page-num page-end
                                  :parent-section-id parent-id
                                  :id section-id)
            sections' (conj sections section)
            anchors' (conj anchors [page-num block-idx])
            sections''
            (if (#{"chapter" "banner"} tier)
              (reparent-same-page-subordinates sections' section-id page-num subordinate-ids)
              sections')
            stack'
            (cond
              (= tier "meta") stack
              (and (= tier "subordinate") parent-id) stack
              :else
              (let [stack-level (if (and (= tier "subordinate") (nil? parent-id))
                                  (dec level')
                                  level')]
                (conj (pop-stack-to-level stack stack-level) [stack-level section-id])))
            active-chapter-id'
            (if (#{"chapter" "banner"} tier) section-id active-chapter-id)
            subordinate-ids'
            (cond
              (#{"chapter" "banner"} tier) #{}
              (= tier "subordinate") (conj subordinate-ids section-id)
              :else subordinate-ids)]
        (recur (rest remaining) sections'' anchors' stack' active-chapter-id' subordinate-ids')))))

(defn- section-for-body-block
  [pages page-num block block-idx sections anchors]
  (or
   (some
    (fn [[anchor sec]]
      (let [[anchor-page anchor-idx] anchor]
        (when (= anchor-page page-num)
          (let [heading-block (ro/find-block pages anchor-page anchor-idx)]
            (when (and heading-block
                       (ro/is-in-column-band? block heading-block)
                       (<= (get-in heading-block [:bbox :y0]) (get-in block [:bbox :y0])))
              (:id sec))))))
    (reverse (map vector anchors sections)))
   (some
    (fn [[anchor sec]]
      (let [[anchor-page anchor-idx] anchor]
        (when (and (<= anchor-page page-num)
                   (or (< anchor-page page-num)
                       (<= anchor-idx block-idx)))
          (let [heading-block (ro/find-block pages anchor-page anchor-idx)]
            (when (and heading-block (ro/is-in-column-band? block heading-block))
              (:id sec))))))
    (reverse (map vector anchors sections)))
   (:id (first sections))))

(defn- assign-body-blocks
  [pages sections anchors document-id content-only-ids]
  (let [content-only-anchors
        (set (keep-indexed
              (fn [i _] (when (contains? content-only-ids (:id (nth sections i)))
                          (nth anchors i)))
              sections))
        heading-positions (set/difference (set anchors) content-only-anchors)]
    (into {}
          (for [page pages
                :let [page-num (:page-number page)]
                block (:blocks page)
                :let [idx (:block-index block)]
                :when (not (contains? heading-positions [page-num idx]))]
            [(block-id document-id page-num idx)
             (section-for-body-block pages page-num block idx sections anchors)]))))

(defn assign-sections
  [pages {:keys [campaign-id document-id]}]
  (let [pages (ro/normalize-reading-order pages)
        page-count (if (seq pages) (:page-number (last pages)) 1)
        page-medians (into {} (map (fn [p] [(:page-number p) (ro/page-median-font (:blocks p))]) pages))
        headings
        (vec
         (for [page pages
               :let [median (get page-medians (:page-number page))]
               [idx block] (map-indexed vector (:blocks page))
               :when (heading-candidate? block page median (:blocks page) idx)]
           [(:page-number page) (:block-index block) (str/trim (:text block))
            (heading-level (str/trim (:text block)) block median)]))]
    (if (empty? headings)
      (let [fallback (make-section campaign-id document-id "Document" 1
                                   (or (:page-number (first pages)) 1) page-count)]
        {:sections [fallback]
         :heading-anchors []
         :block-assignments
         (into {}
               (for [page pages block (:blocks page)]
                 [(block-id document-id (:page-number page) (:block-index block))
                  (:id fallback)]))
         :content-only-section-ids #{}})
      (let [sorted (spatially-sorted-headings headings pages)
            {:keys [sections anchors]}
            (build-sections-from-headings sorted pages campaign-id document-id page-count page-medians)
            heading-positions (set anchors)
            {:keys [preamble-sections preamble-anchors content-only-ids]}
            (detect-preamble-sections pages heading-positions campaign-id document-id)
            merged (merge-preamble sections anchors preamble-sections preamble-anchors content-only-ids)
            final-sections (:sections merged)
            final-anchors (:anchors merged)]
        {:sections final-sections
         :heading-anchors final-anchors
         :block-assignments
         (assign-body-blocks pages final-sections final-anchors document-id (:content-only-ids merged))
         :content-only-section-ids (:content-only-ids merged)}))))
