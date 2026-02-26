TCSS = """
#main {
    width: 1fr;
    height: 1fr;
    margin: 1 1;
}

#collection-card {
    width: 40;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    padding: 0 1;
}

#doc-tree {
    width: 1fr;
}

#detail-card {
    width: 1fr;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    margin-left: 1;
    padding: 0;
    overflow-y: auto;
}

#content {
    width: 1fr;
    padding: 1 2;
    color: $text;
}

#meta-header {
    width: 1fr;
    padding: 1 2;
    background: $primary-background-lighten-1;
    color: $text-muted;
    height: auto;
    max-height: 5;
}

#md-content {
    width: 1fr;
    padding: 1 2;
}

#run-bar {
    height: 5;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    margin: 0 1;
    padding: 0 2;
}

#run-bar-inner {
    height: 1fr;
    align: left middle;
}

#selection-count {
    width: auto;
    padding: 0 2;
    color: $text-muted;
}

#iterations-label {
    width: auto;
    padding: 0 1;
    color: $text-muted;
}

#iterations-input {
    width: 8;
}

#run-hint {
    width: auto;
    padding: 0 2;
    color: $text-muted;
}
"""
