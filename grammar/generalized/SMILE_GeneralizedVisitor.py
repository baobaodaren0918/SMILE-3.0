# Generated from SMILE_Generalized.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SMILE_GeneralizedParser import SMILE_GeneralizedParser
else:
    from SMILE_GeneralizedParser import SMILE_GeneralizedParser

# This class defines a complete generic visitor for a parse tree produced by SMILE_GeneralizedParser.

class SMILE_GeneralizedVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SMILE_GeneralizedParser#migration.
    def visitMigration(self, ctx:SMILE_GeneralizedParser.MigrationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#header.
    def visitHeader(self, ctx:SMILE_GeneralizedParser.HeaderContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#migrationDecl.
    def visitMigrationDecl(self, ctx:SMILE_GeneralizedParser.MigrationDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#evolutionDecl.
    def visitEvolutionDecl(self, ctx:SMILE_GeneralizedParser.EvolutionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#fromToDecl.
    def visitFromToDecl(self, ctx:SMILE_GeneralizedParser.FromToDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#usingDecl.
    def visitUsingDecl(self, ctx:SMILE_GeneralizedParser.UsingDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#databaseType.
    def visitDatabaseType(self, ctx:SMILE_GeneralizedParser.DatabaseTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#version.
    def visitVersion(self, ctx:SMILE_GeneralizedParser.VersionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#operation.
    def visitOperation(self, ctx:SMILE_GeneralizedParser.OperationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#add_gen.
    def visitAdd_gen(self, ctx:SMILE_GeneralizedParser.Add_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyAdd.
    def visitPropertyAdd(self, ctx:SMILE_GeneralizedParser.PropertyAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyClause.
    def visitPropertyClause(self, ctx:SMILE_GeneralizedParser.PropertyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withTypeClause.
    def visitWithTypeClause(self, ctx:SMILE_GeneralizedParser.WithTypeClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withDefaultClause.
    def visitWithDefaultClause(self, ctx:SMILE_GeneralizedParser.WithDefaultClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#notNullClause.
    def visitNotNullClause(self, ctx:SMILE_GeneralizedParser.NotNullClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#foreignKeyAdd.
    def visitForeignKeyAdd(self, ctx:SMILE_GeneralizedParser.ForeignKeyAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#constraintClause.
    def visitConstraintClause(self, ctx:SMILE_GeneralizedParser.ConstraintClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#embeddedAdd.
    def visitEmbeddedAdd(self, ctx:SMILE_GeneralizedParser.EmbeddedAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#embeddedClause.
    def visitEmbeddedClause(self, ctx:SMILE_GeneralizedParser.EmbeddedClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withStructureClause.
    def visitWithStructureClause(self, ctx:SMILE_GeneralizedParser.WithStructureClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityAdd.
    def visitEntityAdd(self, ctx:SMILE_GeneralizedParser.EntityAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityClause.
    def visitEntityClause(self, ctx:SMILE_GeneralizedParser.EntityClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withKeyClause.
    def visitWithKeyClause(self, ctx:SMILE_GeneralizedParser.WithKeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#keyAdd.
    def visitKeyAdd(self, ctx:SMILE_GeneralizedParser.KeyAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#keyColumns.
    def visitKeyColumns(self, ctx:SMILE_GeneralizedParser.KeyColumnsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#labelAdd.
    def visitLabelAdd(self, ctx:SMILE_GeneralizedParser.LabelAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#constraintAdd.
    def visitConstraintAdd(self, ctx:SMILE_GeneralizedParser.ConstraintAddContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyReference.
    def visitConstraintBodyReference(self, ctx:SMILE_GeneralizedParser.ConstraintBodyReferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyCheck.
    def visitConstraintBodyCheck(self, ctx:SMILE_GeneralizedParser.ConstraintBodyCheckContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#ConstraintBodyExistence.
    def visitConstraintBodyExistence(self, ctx:SMILE_GeneralizedParser.ConstraintBodyExistenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckParenExpr.
    def visitCheckParenExpr(self, ctx:SMILE_GeneralizedParser.CheckParenExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckAtomExpr.
    def visitCheckAtomExpr(self, ctx:SMILE_GeneralizedParser.CheckAtomExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckAndExpr.
    def visitCheckAndExpr(self, ctx:SMILE_GeneralizedParser.CheckAndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckOrExpr.
    def visitCheckOrExpr(self, ctx:SMILE_GeneralizedParser.CheckOrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckNotExpr.
    def visitCheckNotExpr(self, ctx:SMILE_GeneralizedParser.CheckNotExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CheckRawExpr.
    def visitCheckRawExpr(self, ctx:SMILE_GeneralizedParser.CheckRawExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#CmpAtom.
    def visitCmpAtom(self, ctx:SMILE_GeneralizedParser.CmpAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#InAtom.
    def visitInAtom(self, ctx:SMILE_GeneralizedParser.InAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#BetweenAtom.
    def visitBetweenAtom(self, ctx:SMILE_GeneralizedParser.BetweenAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#RegexAtom.
    def visitRegexAtom(self, ctx:SMILE_GeneralizedParser.RegexAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#IsNullAtom.
    def visitIsNullAtom(self, ctx:SMILE_GeneralizedParser.IsNullAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#IsNotNullAtom.
    def visitIsNotNullAtom(self, ctx:SMILE_GeneralizedParser.IsNotNullAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#cmpOp.
    def visitCmpOp(self, ctx:SMILE_GeneralizedParser.CmpOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#literalList.
    def visitLiteralList(self, ctx:SMILE_GeneralizedParser.LiteralListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#delete_gen.
    def visitDelete_gen(self, ctx:SMILE_GeneralizedParser.Delete_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyDelete.
    def visitPropertyDelete(self, ctx:SMILE_GeneralizedParser.PropertyDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#foreignKeyDelete.
    def visitForeignKeyDelete(self, ctx:SMILE_GeneralizedParser.ForeignKeyDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#embeddedDelete.
    def visitEmbeddedDelete(self, ctx:SMILE_GeneralizedParser.EmbeddedDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityDelete.
    def visitEntityDelete(self, ctx:SMILE_GeneralizedParser.EntityDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#keyDelete.
    def visitKeyDelete(self, ctx:SMILE_GeneralizedParser.KeyDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#labelDelete.
    def visitLabelDelete(self, ctx:SMILE_GeneralizedParser.LabelDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#constraintDelete.
    def visitConstraintDelete(self, ctx:SMILE_GeneralizedParser.ConstraintDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#rename_gen.
    def visitRename_gen(self, ctx:SMILE_GeneralizedParser.Rename_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyRename.
    def visitPropertyRename(self, ctx:SMILE_GeneralizedParser.PropertyRenameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityRename.
    def visitEntityRename(self, ctx:SMILE_GeneralizedParser.EntityRenameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#keyType.
    def visitKeyType(self, ctx:SMILE_GeneralizedParser.KeyTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#keyClause.
    def visitKeyClause(self, ctx:SMILE_GeneralizedParser.KeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#referencesClause.
    def visitReferencesClause(self, ctx:SMILE_GeneralizedParser.ReferencesClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withColumnsClause.
    def visitWithColumnsClause(self, ctx:SMILE_GeneralizedParser.WithColumnsClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#identifierList.
    def visitIdentifierList(self, ctx:SMILE_GeneralizedParser.IdentifierListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#flatten_gen.
    def visitFlatten_gen(self, ctx:SMILE_GeneralizedParser.Flatten_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unflatten_gen.
    def visitUnflatten_gen(self, ctx:SMILE_GeneralizedParser.Unflatten_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unnest_gen.
    def visitUnnest_gen(self, ctx:SMILE_GeneralizedParser.Unnest_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unnestCarryList.
    def visitUnnestCarryList(self, ctx:SMILE_GeneralizedParser.UnnestCarryListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unnestCarryField.
    def visitUnnestCarryField(self, ctx:SMILE_GeneralizedParser.UnnestCarryFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unnestFieldList.
    def visitUnnestFieldList(self, ctx:SMILE_GeneralizedParser.UnnestFieldListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#SimpleField.
    def visitSimpleField(self, ctx:SMILE_GeneralizedParser.SimpleFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#NestedField.
    def visitNestedField(self, ctx:SMILE_GeneralizedParser.NestedFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#unwind_gen.
    def visitUnwind_gen(self, ctx:SMILE_GeneralizedParser.Unwind_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#wind_gen.
    def visitWind_gen(self, ctx:SMILE_GeneralizedParser.Wind_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#nest_gen.
    def visitNest_gen(self, ctx:SMILE_GeneralizedParser.Nest_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#copy_gen.
    def visitCopy_gen(self, ctx:SMILE_GeneralizedParser.Copy_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyCopy.
    def visitPropertyCopy(self, ctx:SMILE_GeneralizedParser.PropertyCopyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityCopy.
    def visitEntityCopy(self, ctx:SMILE_GeneralizedParser.EntityCopyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#move_gen.
    def visitMove_gen(self, ctx:SMILE_GeneralizedParser.Move_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#merge_gen.
    def visitMerge_gen(self, ctx:SMILE_GeneralizedParser.Merge_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#split_gen.
    def visitSplit_gen(self, ctx:SMILE_GeneralizedParser.Split_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#splitPartGen.
    def visitSplitPartGen(self, ctx:SMILE_GeneralizedParser.SplitPartGenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#cast_gen.
    def visitCast_gen(self, ctx:SMILE_GeneralizedParser.Cast_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyCast.
    def visitPropertyCast(self, ctx:SMILE_GeneralizedParser.PropertyCastContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#constraintCast.
    def visitConstraintCast(self, ctx:SMILE_GeneralizedParser.ConstraintCastContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#entityCast.
    def visitEntityCast(self, ctx:SMILE_GeneralizedParser.EntityCastContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#recard_gen.
    def visitRecard_gen(self, ctx:SMILE_GeneralizedParser.Recard_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#transform_gen.
    def visitTransform_gen(self, ctx:SMILE_GeneralizedParser.Transform_genContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#TransformToRelationship.
    def visitTransformToRelationship(self, ctx:SMILE_GeneralizedParser.TransformToRelationshipContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#TransformToEntity.
    def visitTransformToEntity(self, ctx:SMILE_GeneralizedParser.TransformToEntityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withCardinalityClause.
    def visitWithCardinalityClause(self, ctx:SMILE_GeneralizedParser.WithCardinalityClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#usingKeyClause.
    def visitUsingKeyClause(self, ctx:SMILE_GeneralizedParser.UsingKeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#whereClause.
    def visitWhereClause(self, ctx:SMILE_GeneralizedParser.WhereClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#withPropertiesClause.
    def visitWithPropertiesClause(self, ctx:SMILE_GeneralizedParser.WithPropertiesClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyDefList.
    def visitPropertyDefList(self, ctx:SMILE_GeneralizedParser.PropertyDefListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#propertyDef.
    def visitPropertyDef(self, ctx:SMILE_GeneralizedParser.PropertyDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#cardinalityType.
    def visitCardinalityType(self, ctx:SMILE_GeneralizedParser.CardinalityTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#constraintKeyType.
    def visitConstraintKeyType(self, ctx:SMILE_GeneralizedParser.ConstraintKeyTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#dataType.
    def visitDataType(self, ctx:SMILE_GeneralizedParser.DataTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#qualifiedName.
    def visitQualifiedName(self, ctx:SMILE_GeneralizedParser.QualifiedNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#pathSegment.
    def visitPathSegment(self, ctx:SMILE_GeneralizedParser.PathSegmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#identifier.
    def visitIdentifier(self, ctx:SMILE_GeneralizedParser.IdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#condition.
    def visitCondition(self, ctx:SMILE_GeneralizedParser.ConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#equalityCondition.
    def visitEqualityCondition(self, ctx:SMILE_GeneralizedParser.EqualityConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#edgeCondition.
    def visitEdgeCondition(self, ctx:SMILE_GeneralizedParser.EdgeConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_GeneralizedParser#literal.
    def visitLiteral(self, ctx:SMILE_GeneralizedParser.LiteralContext):
        return self.visitChildren(ctx)



del SMILE_GeneralizedParser