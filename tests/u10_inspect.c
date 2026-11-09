/* Test-only GTK widget snapshot. Enabled solely by U10_INSPECT_FILE. */
#include <gtk/gtk.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static FILE *out;
static GtkWidget *top;
static void value(const char *s) {
    gchar *b = g_base64_encode((const guchar *)(s ? s : ""), s ? strlen(s) : 0);
    fprintf(out, "\t%s", b); g_free(b);
}
static void rows(GtkTreeView *view, GtkTreeModel *model, GtkTreeIter *iter) {
    do {
        GtkTreePath *path = gtk_tree_model_get_path(model, iter);
        gchar *p = gtk_tree_path_to_string(path);
        GtkTreeSelection *selection = gtk_tree_view_get_selection(view);
        fprintf(out, "ROW\t%p\t%d\t%d", (void *)view,
                gtk_tree_selection_iter_is_selected(selection, iter),
                gtk_tree_view_row_expanded(view, path));
        value(p); g_free(p);
        for (int i = 0; i < gtk_tree_model_get_n_columns(model); ++i) {
            if (gtk_tree_model_get_column_type(model, i) == G_TYPE_STRING) {
                gchar *s = NULL; gtk_tree_model_get(model, iter, i, &s, -1);
                value(s); g_free(s);
            }
        }
        fputc('\n', out); gtk_tree_path_free(path);
        GtkTreeIter child;
        if (gtk_tree_model_iter_children(model, &child, iter)) rows(view, model, &child);
    } while (gtk_tree_model_iter_next(model, iter));
}
static void walk(GtkWidget *w) {
    if (!gtk_widget_get_visible(w) || !gtk_widget_get_mapped(w)) return;
    int x = 0, y = 0; GtkAllocation a; gtk_widget_get_allocation(w, &a);
    gtk_widget_translate_coordinates(w, top, 0, 0, &x, &y);
    fprintf(out, "W\t%p\t%s\t%d\t%d\t%d\t%d", (void *)w, G_OBJECT_TYPE_NAME(w), x, y, a.width, a.height);
    if (GTK_IS_LABEL(w)) value(gtk_label_get_text(GTK_LABEL(w)));
    else if (GTK_IS_TEXT_VIEW(w)) {
        GtkTextBuffer *b = gtk_text_view_get_buffer(GTK_TEXT_VIEW(w)); GtkTextIter a1, b1;
        gtk_text_buffer_get_bounds(b, &a1, &b1);
        gchar *s = gtk_text_buffer_get_text(b, &a1, &b1, FALSE); value(s); g_free(s);
    } else value("");
    if (GTK_IS_NOTEBOOK(w)) fprintf(out, "\t%d", gtk_notebook_get_current_page(GTK_NOTEBOOK(w)));
    fputc('\n', out);
    if (GTK_IS_TREE_VIEW(w)) {
        GtkTreeModel *model = gtk_tree_view_get_model(GTK_TREE_VIEW(w)); GtkTreeIter i;
        if (model && gtk_tree_model_get_iter_first(model, &i)) rows(GTK_TREE_VIEW(w), model, &i);
    }
    if (GTK_IS_CONTAINER(w)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(w));
        for (GList *i = children; i; i = i->next) walk(GTK_WIDGET(i->data));
        g_list_free(children);
    }
}
static gboolean snapshot(gpointer unused) {
    (void)unused; const char *name = getenv("U10_INSPECT_FILE");
    if (!name) return G_SOURCE_CONTINUE;
    gchar *tmp = g_strconcat(name, ".tmp", NULL);
    out = fopen(tmp, "w");
    if (!out) { g_free(tmp); return G_SOURCE_CONTINUE; }
    GList *windows = gtk_window_list_toplevels();
    for (GList *i = windows; i; i = i->next) {
        top = GTK_WIDGET(i->data); if (gtk_widget_get_mapped(top)) walk(top);
    }
    g_list_free(windows); fclose(out); rename(tmp, name); g_free(tmp);
    return G_SOURCE_CONTINUE;
}
__attribute__((constructor)) static void start(void) { if (getenv("U10_INSPECT_FILE")) g_timeout_add(150, snapshot, NULL); }
