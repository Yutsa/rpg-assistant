(ns rpg-assistant-web.test-helpers)

(defn- hiccup-tag [node]
  (when (vector? node) (first node)))

(defn- hiccup-children [node]
  (when (vector? node)
    (drop (if (map? (second node)) 2 1) node)))

(defn- hiccup-node? [x]
  (vector? x))

(defn walk-hiccup
  "Parcourt l'arbre hiccup et appelle f sur chaque nœud vecteur."
  [node f]
  (when (hiccup-node? node)
    (f node)
    (doseq [child (hiccup-children node)]
      (cond
        (hiccup-node? child) (walk-hiccup child f)
        (sequential? child) (doseq [nested child]
                              (when (hiccup-node? nested)
                                (walk-hiccup nested f)))))))

(defn find-first
  [pred node]
  (when (hiccup-node? node)
    (or (when (pred node) node)
        (some
         (fn [child]
           (cond
             (hiccup-node? child) (find-first pred child)
             (sequential? child) (some #(find-first pred %) child)))
         (hiccup-children node)))))

(defn hiccup-texts
  "Collecte les chaînes texte de l'arbre hiccup."
  [node]
  (cond
    (string? node) [node]
    (hiccup-node? node)
    (mapcat hiccup-texts (hiccup-children node))

    (sequential? node)
    (mapcat hiccup-texts node)

    :else []))

(defn main-h2-text
  "Titre h2 principal sous :main.page (Replicant :main.page)."
  [tree]
  (let [in-main? (atom false)
        result (atom nil)]
    (walk-hiccup tree
                  (fn [node]
                    (cond
                      (= :main.page (hiccup-tag node))
                      (reset! in-main? true)

                      (and @in-main? (= :h2 (hiccup-tag node)) (nil? @result))
                      (reset! result (second node)))))
    @result))

(defn shows-campaign-list?
  "Vrai si la vue affiche la grille de campagnes (pas seulement le fil d'Ariane)."
  [tree]
  (let [found (atom false)]
    (walk-hiccup tree #(when (= :div.card-grid (hiccup-tag %)) (reset! found true)))
    @found))
