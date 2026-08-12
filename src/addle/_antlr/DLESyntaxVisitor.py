# Generated from /Users/pag/dev/oss/owl/addle/grammar/DLESyntax.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .DLESyntaxParser import DLESyntaxParser
else:
    from DLESyntaxParser import DLESyntaxParser

# This class defines a complete generic visitor for a parse tree produced by DLESyntaxParser.

class DLESyntaxVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by DLESyntaxParser#ontology.
    def visitOntology(self, ctx:DLESyntaxParser.OntologyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#prefixDecl.
    def visitPrefixDecl(self, ctx:DLESyntaxParser.PrefixDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#ontologyDecl.
    def visitOntologyDecl(self, ctx:DLESyntaxParser.OntologyDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#versionDecl.
    def visitVersionDecl(self, ctx:DLESyntaxParser.VersionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#importDecl.
    def visitImportDecl(self, ctx:DLESyntaxParser.ImportDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#iriRef.
    def visitIriRef(self, ctx:DLESyntaxParser.IriRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#statement.
    def visitStatement(self, ctx:DLESyntaxParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#LabelAnnotation.
    def visitLabelAnnotation(self, ctx:DLESyntaxParser.LabelAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#DocAnnotation.
    def visitDocAnnotation(self, ctx:DLESyntaxParser.DocAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#StorageAnnotation.
    def visitStorageAnnotation(self, ctx:DLESyntaxParser.StorageAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#DbAnnotation.
    def visitDbAnnotation(self, ctx:DLESyntaxParser.DbAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AnnAnnotation.
    def visitAnnAnnotation(self, ctx:DLESyntaxParser.AnnAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#PredicateDefinition.
    def visitPredicateDefinition(self, ctx:DLESyntaxParser.PredicateDefinitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#FolAnnotation.
    def visitFolAnnotation(self, ctx:DLESyntaxParser.FolAnnotationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#StringAnnotationValue.
    def visitStringAnnotationValue(self, ctx:DLESyntaxParser.StringAnnotationValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#IriAnnotationValue.
    def visitIriAnnotationValue(self, ctx:DLESyntaxParser.IriAnnotationValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#HasKeyAxiom.
    def visitHasKeyAxiom(self, ctx:DLESyntaxParser.HasKeyAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#FunctionalPropertyAxiom.
    def visitFunctionalPropertyAxiom(self, ctx:DLESyntaxParser.FunctionalPropertyAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#TransitiveRoleAxiom.
    def visitTransitiveRoleAxiom(self, ctx:DLESyntaxParser.TransitiveRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#FunctionalRoleAxiom.
    def visitFunctionalRoleAxiom(self, ctx:DLESyntaxParser.FunctionalRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#ReflexiveRoleAxiom.
    def visitReflexiveRoleAxiom(self, ctx:DLESyntaxParser.ReflexiveRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#IrreflexiveRoleAxiom.
    def visitIrreflexiveRoleAxiom(self, ctx:DLESyntaxParser.IrreflexiveRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SymmetricRoleAxiom.
    def visitSymmetricRoleAxiom(self, ctx:DLESyntaxParser.SymmetricRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AsymmetricRoleAxiom.
    def visitAsymmetricRoleAxiom(self, ctx:DLESyntaxParser.AsymmetricRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#DisjointRoleAxiom.
    def visitDisjointRoleAxiom(self, ctx:DLESyntaxParser.DisjointRoleAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AnnPropDomainAxiom.
    def visitAnnPropDomainAxiom(self, ctx:DLESyntaxParser.AnnPropDomainAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AnnPropRangeAxiom.
    def visitAnnPropRangeAxiom(self, ctx:DLESyntaxParser.AnnPropRangeAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SubPropertyChainAxiom.
    def visitSubPropertyChainAxiom(self, ctx:DLESyntaxParser.SubPropertyChainAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#PropertyChainEquivAxiom.
    def visitPropertyChainEquivAxiom(self, ctx:DLESyntaxParser.PropertyChainEquivAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#ChainedEquivSubAxiom.
    def visitChainedEquivSubAxiom(self, ctx:DLESyntaxParser.ChainedEquivSubAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SubClassAxiom.
    def visitSubClassAxiom(self, ctx:DLESyntaxParser.SubClassAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#EquivAxiom.
    def visitEquivAxiom(self, ctx:DLESyntaxParser.EquivAxiomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#chainExpr.
    def visitChainExpr(self, ctx:DLESyntaxParser.ChainExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#keyExpr.
    def visitKeyExpr(self, ctx:DLESyntaxParser.KeyExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#InversePropertyExpr.
    def visitInversePropertyExpr(self, ctx:DLESyntaxParser.InversePropertyExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SimplePropertyExpr.
    def visitSimplePropertyExpr(self, ctx:DLESyntaxParser.SimplePropertyExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#IntersectionWrap.
    def visitIntersectionWrap(self, ctx:DLESyntaxParser.IntersectionWrapContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#UnionOf.
    def visitUnionOf(self, ctx:DLESyntaxParser.UnionOfContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#IntersectionOf.
    def visitIntersectionOf(self, ctx:DLESyntaxParser.IntersectionOfContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#PrimaryWrap.
    def visitPrimaryWrap(self, ctx:DLESyntaxParser.PrimaryWrapContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#Complement.
    def visitComplement(self, ctx:DLESyntaxParser.ComplementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#MultiRoleSomeValuesFrom.
    def visitMultiRoleSomeValuesFrom(self, ctx:DLESyntaxParser.MultiRoleSomeValuesFromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#MultiRoleAllValuesFrom.
    def visitMultiRoleAllValuesFrom(self, ctx:DLESyntaxParser.MultiRoleAllValuesFromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SomeValuesFrom.
    def visitSomeValuesFrom(self, ctx:DLESyntaxParser.SomeValuesFromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AllValuesFrom.
    def visitAllValuesFrom(self, ctx:DLESyntaxParser.AllValuesFromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#CardinalityRestriction.
    def visitCardinalityRestriction(self, ctx:DLESyntaxParser.CardinalityRestrictionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#UnqualifiedCardinalityRestriction.
    def visitUnqualifiedCardinalityRestriction(self, ctx:DLESyntaxParser.UnqualifiedCardinalityRestrictionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#ImplicitSomeValuesFrom.
    def visitImplicitSomeValuesFrom(self, ctx:DLESyntaxParser.ImplicitSomeValuesFromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#AtomWrap.
    def visitAtomWrap(self, ctx:DLESyntaxParser.AtomWrapContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#cardSymbol.
    def visitCardSymbol(self, ctx:DLESyntaxParser.CardSymbolContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#NumericDataRangeAtom.
    def visitNumericDataRangeAtom(self, ctx:DLESyntaxParser.NumericDataRangeAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#InversePropertyAtom.
    def visitInversePropertyAtom(self, ctx:DLESyntaxParser.InversePropertyAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#NameAtom.
    def visitNameAtom(self, ctx:DLESyntaxParser.NameAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#TopAtom.
    def visitTopAtom(self, ctx:DLESyntaxParser.TopAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#BottomAtom.
    def visitBottomAtom(self, ctx:DLESyntaxParser.BottomAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#SelfAtom.
    def visitSelfAtom(self, ctx:DLESyntaxParser.SelfAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#OneOfAtom.
    def visitOneOfAtom(self, ctx:DLESyntaxParser.OneOfAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#ParenAtom.
    def visitParenAtom(self, ctx:DLESyntaxParser.ParenAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#EmptyAtom.
    def visitEmptyAtom(self, ctx:DLESyntaxParser.EmptyAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#DataRangeAtom.
    def visitDataRangeAtom(self, ctx:DLESyntaxParser.DataRangeAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#numericFacet.
    def visitNumericFacet(self, ctx:DLESyntaxParser.NumericFacetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#datatypeRestriction.
    def visitDatatypeRestriction(self, ctx:DLESyntaxParser.DatatypeRestrictionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#facet.
    def visitFacet(self, ctx:DLESyntaxParser.FacetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#oneOfList.
    def visitOneOfList(self, ctx:DLESyntaxParser.OneOfListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#IndividualElem.
    def visitIndividualElem(self, ctx:DLESyntaxParser.IndividualElemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#LiteralElem.
    def visitLiteralElem(self, ctx:DLESyntaxParser.LiteralElemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#StringLiteral.
    def visitStringLiteral(self, ctx:DLESyntaxParser.StringLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#NumberLiteral.
    def visitNumberLiteral(self, ctx:DLESyntaxParser.NumberLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#BoolLiteral.
    def visitBoolLiteral(self, ctx:DLESyntaxParser.BoolLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by DLESyntaxParser#name.
    def visitName(self, ctx:DLESyntaxParser.NameContext):
        return self.visitChildren(ctx)



del DLESyntaxParser